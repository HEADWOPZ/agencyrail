from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from agencyrail.config import AppConfig
from agencyrail.models import STATION_ORDER, cents_to_amount
from agencyrail.store import Store

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


@dataclass
class WeeklyDigest:
    week_of: str
    markdown: str
    telegram_text: str
    path: Path | None
    sent: bool
    dry_run: bool


def build_weekly_digest(store: Store, config: AppConfig, home: Path | None = None) -> WeeklyDigest:
    now = datetime.now(timezone.utc)
    week_of = (now - timedelta(days=now.weekday())).date().isoformat()
    leads = store.list_leads()
    counts = store.counts_by_status()
    invoices = store.list_invoices()
    events = store.list_events(limit=80)
    cutoff = (now - timedelta(days=7)).isoformat()

    new_leads = [lead for lead in leads if lead.created_at >= cutoff]
    moved = [event for event in events if event.created_at >= cutoff and event.kind.startswith("lead.")]
    agent_runs = [event for event in events if event.created_at >= cutoff and event.kind.startswith("agent.")]
    open_invoices = [inv for inv in invoices if inv.status in {"draft", "sent"}]
    paid = [inv for inv in invoices if inv.status == "paid"]
    hot = [lead for lead in leads if lead.status in {"outreach", "negotiation", "retainer"}]

    outstanding_cents = sum(inv.amount_cents for inv in open_invoices)
    paid_cents = sum(inv.amount_cents for inv in paid)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2", "md")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    ctx = {
        "week_of": week_of,
        "operator": config.operator,
        "agency": config.agency,
        "counts": counts,
        "stations": STATION_ORDER,
        "new_leads": new_leads,
        "hot": hot,
        "moved": moved,
        "agent_runs": agent_runs,
        "open_invoices": open_invoices,
        "outstanding": cents_to_amount(outstanding_cents),
        "collected": cents_to_amount(paid_cents),
        "leads": leads,
        "lead_by_id": {lead.id: lead for lead in leads},
    }
    markdown = env.get_template("telegram_digest.md.j2").render(**ctx).strip() + "\n"
    telegram_text = _telegram_plain(ctx)

    path = None
    if home is not None:
        folder = home / "digests"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"weekly-{week_of}.md"
        path.write_text(markdown, encoding="utf-8")

    return WeeklyDigest(
        week_of=week_of,
        markdown=markdown,
        telegram_text=telegram_text,
        path=path,
        sent=False,
        dry_run=True,
    )


def send_telegram(text: str, token: str, chat_id: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = httpx.post(
        url,
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _telegram_plain(ctx: dict) -> str:
    counts = ctx["counts"]
    rail = " → ".join(f"{station[:3].upper()} {counts[station]}" for station in ctx["stations"])
    lines = [
        f"AgencyRail · week of {ctx['week_of']}",
        rail,
        f"Outstanding {ctx['outstanding']} {ctx['agency'].currency} · collected {ctx['collected']}",
    ]
    if ctx["hot"]:
        lines.append("Hot:")
        for lead in ctx["hot"][:5]:
            lines.append(f"• {lead.org} [{lead.status}] — {lead.next_action}")
    if ctx["new_leads"]:
        names = ", ".join(lead.org for lead in ctx["new_leads"][:6])
        lines.append(f"New: {names}")
    lines.append(f"Agents ran {len(ctx['agent_runs'])} jobs this week.")
    lines.append(f"— {ctx['operator'].name}")
    return "\n".join(lines)
