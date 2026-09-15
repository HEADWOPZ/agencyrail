from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agencyrail.config import AppConfig
from agencyrail.models import Invoice, Lead, cents_to_amount, parse_amount_to_cents
from agencyrail.store import Store

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def stub_checkout_url(number: str) -> str:
    token = number.lower().replace("_", "-")
    return f"https://checkout.stripe.com/c/pay/stub_agencyrail_{token}"


def create_invoice(
    store: Store,
    config: AppConfig,
    lead: Lead,
    amount: str | int | float | None = None,
    days_until_due: int = 7,
) -> Invoice:
    if amount is not None:
        cents = parse_amount_to_cents(amount)
    elif lead.retainer_cents:
        cents = lead.retainer_cents
    else:
        cents = config.agency.default_retainer_cents

    now = datetime.now(timezone.utc)
    number = store.next_invoice_number(config.agency.invoice_prefix, now.year)
    due = (now + timedelta(days=days_until_due)).date().isoformat()
    stripe_url = stub_checkout_url(number) if config.integrations.stripe_mode == "stub" else None

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2", "md")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    markdown = env.get_template("invoice.md.j2").render(
        invoice_number=number,
        lead=lead,
        operator=config.operator,
        agency=config.agency,
        amount=cents_to_amount(cents),
        currency=lead.currency or config.agency.currency,
        due_on=due,
        stripe_url=stripe_url,
        issued_on=now.date().isoformat(),
        cadence=lead.retainer_cadence,
    ).strip() + "\n"

    invoice = store.add_invoice(
        number=number,
        lead_id=lead.id,
        amount_cents=cents,
        currency=lead.currency or config.agency.currency,
        status="draft",
        due_on=due,
        stripe_url=stripe_url,
        markdown=markdown,
    )
    store.add_event(
        lead.id,
        "invoice.created",
        f"{invoice.number} · {invoice.currency} {cents_to_amount(cents)}",
    )
    if lead.status not in {"closed", "lost"}:
        store.update_lead(
            lead.slug,
            retainer_cents=cents,
            next_action="Send the retainer invoice and confirm the close",
        )
    return invoice


def write_invoice_markdown(home: Path, invoice: Invoice, lead: Lead) -> Path:
    folder = home / "invoices"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{invoice.number}-{lead.slug}.md"
    path.write_text(invoice.markdown, encoding="utf-8")
    return path
