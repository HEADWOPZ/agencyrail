from __future__ import annotations

from pathlib import Path
from typing import Any

from agencyrail.agents.pack import AgentPack
from agencyrail.billing.invoices import create_invoice, write_invoice_markdown
from agencyrail.config import AppConfig, default_config, default_home, write_example_config
from agencyrail.digest.telegram import WeeklyDigest, build_weekly_digest, send_telegram
from agencyrail.models import ARTIFACT_KINDS, Artifact, Invoice, Lead, parse_amount_to_cents
from agencyrail.seed import seed_demo
from agencyrail.store import Store


class Rail:
    """Facade for CRM, agents, invoices, and the weekly digest."""

    def __init__(self, home: Path | None = None, config: AppConfig | None = None):
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        write_example_config(self.home)
        (self.home / "invoices").mkdir(exist_ok=True)
        (self.home / "digests").mkdir(exist_ok=True)
        self.config = config or default_config()
        self.store = Store(self.home / "agencyrail.db")
        self.pack = AgentPack(self.store, self.config)

    @classmethod
    def init(cls, home: Path | None = None) -> "Rail":
        return cls(home=home)

    def close(self) -> None:
        self.store.close()

    def meta(self) -> dict[str, Any]:
        return {
            "agency": {
                "name": self.config.agency.name,
                "tagline": self.config.agency.tagline,
                "currency": self.config.agency.currency,
            },
            "operator": {
                "name": self.config.operator.name,
                "handle": self.config.operator.handle,
                "email": self.config.operator.email,
                "telegram": self.config.operator.telegram,
                "x": self.config.operator.x,
            },
            "home": str(self.home),
            "stripe_mode": self.config.integrations.stripe_mode,
        }

    def add_lead(self, **kwargs) -> Lead:
        if "retainer" in kwargs and kwargs["retainer"] is not None:
            kwargs["retainer_cents"] = parse_amount_to_cents(kwargs.pop("retainer"))
        kwargs.pop("retainer", None)
        return self.store.add_lead(**kwargs)

    def list_leads(self, **kwargs) -> list[Lead]:
        return self.store.list_leads(**kwargs)

    def get_lead(self, slug_or_id: str | int) -> Lead:
        return self.store.require_lead(slug_or_id)

    def update_lead(self, slug_or_id: str | int, **fields) -> Lead:
        if "retainer" in fields and fields["retainer"] is not None:
            fields["retainer_cents"] = parse_amount_to_cents(fields.pop("retainer"))
        return self.store.update_lead(slug_or_id, **fields)

    def move_lead(self, slug_or_id: str | int, status: str) -> Lead:
        return self.store.move_lead(slug_or_id, status)

    def retain(self, slug_or_id: str | int, amount: str | int | float, cadence: str = "monthly") -> Lead:
        cents = parse_amount_to_cents(amount)
        lead = self.store.update_lead(
            slug_or_id,
            retainer_cents=cents,
            retainer_cadence=cadence,
        )
        return self.store.move_lead(lead.slug, "retainer")

    def run_agent(self, slug_or_id: str | int, kind: str) -> tuple[Lead, Artifact]:
        lead = self.store.require_lead(slug_or_id)
        if kind == "pack":
            raise ValueError("use run_pack for the full set")
        return self.pack.run(lead, kind)

    def run_pack(self, slug_or_id: str | int) -> tuple[Lead, list[Artifact]]:
        lead = self.store.require_lead(slug_or_id)
        artifacts = self.pack.run_all(lead)
        return self.store.require_lead(lead.slug), artifacts

    def list_artifacts(self, slug_or_id: str | int | None = None, kind: str | None = None) -> list[Artifact]:
        lead_id = None
        if slug_or_id is not None:
            lead_id = self.store.require_lead(slug_or_id).id
        return self.store.list_artifacts(lead_id=lead_id, kind=kind)

    def invoice(self, slug_or_id: str | int, amount: str | int | float | None = None) -> tuple[Invoice, Path]:
        lead = self.store.require_lead(slug_or_id)
        invoice = create_invoice(self.store, self.config, lead, amount=amount)
        path = write_invoice_markdown(self.home, invoice, lead)
        return invoice, path

    def list_invoices(self, **kwargs) -> list[Invoice]:
        return self.store.list_invoices(**kwargs)

    def pay_invoice(self, number: str) -> Invoice:
        invoice = self.store.set_invoice_status(number, "paid")
        lead = self.store.get_lead(invoice.lead_id)
        if lead.status not in {"closed", "lost"}:
            self.store.move_lead(lead.slug, "retainer")
        self.store.add_event(lead.id, "invoice.paid", invoice.number)
        return invoice

    def send_invoice(self, number: str) -> Invoice:
        invoice = self.store.set_invoice_status(number, "sent")
        self.store.add_event(invoice.lead_id, "invoice.sent", invoice.number)
        return invoice

    def digest(self, send: bool = False) -> WeeklyDigest:
        digest = build_weekly_digest(self.store, self.config, home=self.home)
        token = self.config.integrations.telegram_bot_token
        chat_id = self.config.integrations.telegram_chat_id
        if send:
            if not token or not chat_id:
                raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required to send")
            send_telegram(digest.telegram_text, token, chat_id)
            digest.sent = True
            digest.dry_run = False
            self.store.add_event(None, "digest.sent", f"week of {digest.week_of}")
        else:
            self.store.add_event(None, "digest.dry_run", f"week of {digest.week_of}")
        return digest

    def seed(self, force: bool = False) -> list[str]:
        slugs = seed_demo(self.store, force=force)
        if slugs:
            self.store.add_event(None, "seed", f"loaded {len(slugs)} demo leads")
        return slugs

    def overview(self) -> dict[str, Any]:
        leads = self.store.list_leads()
        return {
            "counts": self.store.counts_by_status(),
            "leads": [lead.to_dict() for lead in leads],
            "invoices": [inv.to_dict() for inv in self.store.list_invoices()],
            "events": [event.to_dict() for event in self.store.list_events(limit=30)],
            "kinds": list(ARTIFACT_KINDS),
        }
