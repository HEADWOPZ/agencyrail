from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agencyrail import __version__
from agencyrail.config import default_home
from agencyrail.models import (
    ARTIFACT_KINDS,
    CADENCES,
    CHAINS,
    SEGMENTS,
    STATION_ORDER,
    STATUSES,
    cents_to_amount,
)
from agencyrail.rail import Rail

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    help="AgencyRail — crypto-native AI agency ops. Intake to retainer.",
)
lead_app = typer.Typer(help="CRM-lite: leads, status, retainer.")
run_app = typer.Typer(help="Agent pack: audit, mockup, outreach, loom.")
invoice_app = typer.Typer(help="Invoice hooks: markdown + Stripe stub.")
app.add_typer(lead_app, name="lead")
app.add_typer(run_app, name="run")
app.add_typer(invoice_app, name="invoice")

console = Console()


def _rail(home: Optional[Path]) -> Rail:
    return Rail(home=home or default_home())


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"agencyrail {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    home: Optional[Path] = typer.Option(
        None,
        "--home",
        envvar="AGENCYRAIL_HOME",
        help="Data directory (default: ./.agencyrail).",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    ctx.obj = {"home": home}
    if ctx.invoked_subcommand is None:
        status_cmd(home=home)


@app.command("init")
def init_cmd(
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Create the local SQLite workspace and example config."""
    rail = _rail(home)
    console.print(f"Initialized [bold]{rail.home}[/bold]")
    console.print("Operator:", rail.config.operator.name)


@app.command("seed")
def seed_cmd(
    force: bool = typer.Option(False, "--force", help="Add demo leads even if the CRM is not empty."),
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Load a demo rail of wallet / protocol / dApp / docs leads."""
    rail = _rail(home)
    slugs = rail.seed(force=force)
    if not slugs:
        console.print("CRM already has leads. Pass --force to append the demo set.")
        return
    console.print(f"Seeded {len(slugs)} leads: {', '.join(slugs)}")


@app.command("status")
def status_cmd(
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Show the rail: stations, leads, open invoices."""
    rail = _rail(home)
    counts = rail.store.counts_by_status()
    rail_line = Text()
    for i, station in enumerate(STATION_ORDER):
        if i:
            rail_line.append("  ·  ", style="dim")
        rail_line.append(station.upper(), style="bold #e8b86d")
        rail_line.append(f" {counts[station]}", style="white")
    console.print(
        Panel(
            rail_line,
            title=f"{rail.config.agency.name} · {rail.config.operator.name}",
            subtitle=rail.config.agency.tagline,
            border_style="#e8b86d",
        )
    )

    leads = rail.list_leads()
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("slug")
    table.add_column("org")
    table.add_column("seg")
    table.add_column("status")
    table.add_column("score", justify="right")
    table.add_column("retainer", justify="right")
    table.add_column("next")
    if not leads:
        console.print("No leads yet. Try [bold]agencyrail seed[/bold] or [bold]agencyrail lead add[/bold].")
    else:
        for lead in leads:
            retainer = (
                f"{lead.currency} {cents_to_amount(lead.retainer_cents)}"
                if lead.retainer_cents
                else "—"
            )
            table.add_row(
                lead.slug,
                lead.org,
                lead.segment,
                lead.status,
                str(lead.score) if lead.score is not None else "—",
                retainer,
                (lead.next_action or "—")[:48],
            )
        console.print(table)


@lead_app.command("add")
def lead_add(
    name: str = typer.Option(..., "--name", "-n"),
    org: str = typer.Option(..., "--org", "-o"),
    segment: str = typer.Option(..., "--segment", "-s", help="protocol | wallet | dapp | docs"),
    chain: str = typer.Option("multi", "--chain", "-c"),
    email: Optional[str] = typer.Option(None, "--email"),
    telegram: Optional[str] = typer.Option(None, "--telegram"),
    twitter: Optional[str] = typer.Option(None, "--twitter"),
    website: Optional[str] = typer.Option(None, "--website"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Open a new intake."""
    if segment not in SEGMENTS:
        raise typer.BadParameter(f"segment must be one of {', '.join(SEGMENTS)}")
    if chain not in CHAINS:
        raise typer.BadParameter(f"chain must be one of {', '.join(CHAINS)}")
    rail = _rail(home)
    lead = rail.add_lead(
        name=name,
        org=org,
        segment=segment,
        chain=chain,
        email=email,
        telegram=telegram,
        twitter=twitter,
        website=website,
        notes=notes,
    )
    console.print(f"Intake [bold]{lead.slug}[/bold] · {lead.org} · {lead.status}")


@lead_app.command("list")
def lead_list(
    status: Optional[str] = typer.Option(None, "--status"),
    segment: Optional[str] = typer.Option(None, "--segment"),
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """List leads."""
    rail = _rail(home)
    leads = rail.list_leads(status=status, segment=segment)
    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("slug")
    table.add_column("org")
    table.add_column("contact")
    table.add_column("status")
    table.add_column("score", justify="right")
    for lead in leads:
        table.add_row(lead.slug, lead.org, lead.name, lead.status, str(lead.score or "—"))
    console.print(table)
    console.print(f"{len(leads)} lead(s)")


@lead_app.command("show")
def lead_show(
    slug: str = typer.Argument(...),
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Show one lead and its artifacts."""
    rail = _rail(home)
    lead = rail.get_lead(slug)
    console.print(
        Panel(
            "\n".join(
                [
                    f"[bold]{lead.org}[/bold] · {lead.name}",
                    f"{lead.segment} / {lead.chain} · {lead.status}",
                    f"score {lead.score if lead.score is not None else '—'} · next: {lead.next_action}",
                    f"web {lead.website or '—'} · x {lead.twitter or '—'} · tg {lead.telegram or '—'}",
                    f"notes: {lead.notes or '—'}",
                ]
            ),
            border_style="#e8b86d",
        )
    )
    artifacts = rail.list_artifacts(lead.slug)
    if artifacts:
        table = Table(show_header=True, box=None)
        table.add_column("id")
        table.add_column("kind")
        table.add_column("title")
        table.add_column("created")
        for artifact in artifacts:
            table.add_row(str(artifact.id), artifact.kind, artifact.title, artifact.created_at)
        console.print(table)


@lead_app.command("move")
def lead_move(
    slug: str = typer.Argument(...),
    status: str = typer.Argument(...),
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Move a lead to a rail station."""
    if status not in STATUSES:
        raise typer.BadParameter(f"status must be one of {', '.join(STATUSES)}")
    rail = _rail(home)
    lead = rail.move_lead(slug, status)
    console.print(f"{lead.slug} → [bold]{lead.status}[/bold] · {lead.next_action}")


@lead_app.command("retain")
def lead_retain(
    slug: str = typer.Argument(...),
    amount: str = typer.Option(..., "--amount", "-a"),
    cadence: str = typer.Option("monthly", "--cadence"),
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Put a lead on retainer."""
    if cadence not in CADENCES:
        raise typer.BadParameter(f"cadence must be one of {', '.join(CADENCES)}")
    rail = _rail(home)
    lead = rail.retain(slug, amount, cadence=cadence)
    console.print(
        f"{lead.slug} on retainer · {lead.currency} {cents_to_amount(lead.retainer_cents or 0)} / {lead.retainer_cadence}"
    )


@run_app.command("audit")
def run_audit(slug: str, home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME")) -> None:
    """Visibility audit for a wallet / dApp / protocol / docs lead."""
    _run_one(home, slug, "audit")


@run_app.command("mockup")
def run_mockup(slug: str, home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME")) -> None:
    """7-day mockup brief."""
    _run_one(home, slug, "mockup")


@run_app.command("outreach")
def run_outreach(slug: str, home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME")) -> None:
    """Cold email with subject lines."""
    _run_one(home, slug, "outreach")


@run_app.command("loom")
def run_loom(slug: str, home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME")) -> None:
    """90-second Loom script."""
    _run_one(home, slug, "loom")


@run_app.command("pack")
def run_pack(slug: str, home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME")) -> None:
    """Run audit → mockup → outreach → loom."""
    rail = _rail(home)
    lead, artifacts = rail.run_pack(slug)
    console.print(f"[bold]{lead.org}[/bold] pack complete · status {lead.status} · score {lead.score}")
    for artifact in artifacts:
        console.print(f"  {artifact.kind}: {artifact.title}")


def _run_one(home: Optional[Path], slug: str, kind: str) -> None:
    rail = _rail(home)
    lead, artifact = rail.run_agent(slug, kind)
    console.print(
        Panel(
            artifact.body,
            title=f"{KIND_LABEL.get(kind, kind)} · {lead.org}",
            subtitle=f"status {lead.status} · score {lead.score if lead.score is not None else '—'}",
            border_style="#e8b86d",
        )
    )


KIND_LABEL = {kind: kind for kind in ARTIFACT_KINDS}


@invoice_app.command("create")
def invoice_create(
    slug: str = typer.Argument(...),
    amount: Optional[str] = typer.Option(None, "--amount", "-a"),
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Write a markdown invoice and a Stripe Checkout stub URL."""
    rail = _rail(home)
    invoice, path = rail.invoice(slug, amount=amount)
    console.print(f"[bold]{invoice.number}[/bold] · {invoice.currency} {cents_to_amount(invoice.amount_cents)}")
    console.print(f"markdown: {path}")
    if invoice.stripe_url:
        console.print(f"stripe stub: {invoice.stripe_url}")


@invoice_app.command("list")
def invoice_list(
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """List invoices."""
    rail = _rail(home)
    invoices = rail.list_invoices()
    table = Table(show_header=True, box=None)
    table.add_column("number")
    table.add_column("lead")
    table.add_column("amount", justify="right")
    table.add_column("status")
    table.add_column("due")
    for invoice in invoices:
        lead = rail.store.get_lead(invoice.lead_id)
        table.add_row(
            invoice.number,
            lead.org,
            f"{invoice.currency} {cents_to_amount(invoice.amount_cents)}",
            invoice.status,
            invoice.due_on,
        )
    console.print(table)


@invoice_app.command("send")
def invoice_send(
    number: str,
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Mark an invoice sent."""
    rail = _rail(home)
    invoice = rail.send_invoice(number)
    console.print(f"{invoice.number} → sent")


@invoice_app.command("pay")
def invoice_pay(
    number: str,
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Mark an invoice paid and move the lead to retainer."""
    rail = _rail(home)
    invoice = rail.pay_invoice(number)
    console.print(f"{invoice.number} → paid")


@app.command("digest")
def digest_cmd(
    send: bool = typer.Option(False, "--send", help="POST to Telegram. Default is dry-run."),
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Weekly Telegram digest (dry-run writes markdown + prints the message)."""
    rail = _rail(home)
    digest = rail.digest(send=send)
    mode = "sent" if digest.sent else "dry-run"
    console.print(Panel(digest.telegram_text, title=f"Telegram {mode} · week of {digest.week_of}", border_style="#e8b86d"))
    if digest.path:
        console.print(f"markdown: {digest.path}")


@app.command("desk")
def desk_cmd(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
    home: Optional[Path] = typer.Option(None, "--home", envvar="AGENCYRAIL_HOME"),
) -> None:
    """Start the dark desk UI."""
    import os

    import uvicorn

    if home:
        os.environ["AGENCYRAIL_HOME"] = str(home.resolve())
    console.print(f"Desk on http://{host}:{port}  ·  home {home or default_home()}")
    uvicorn.run("agencyrail.desk.app:app", host=host, port=port, reload=False)
