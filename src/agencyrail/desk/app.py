from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agencyrail.models import ARTIFACT_KINDS, CADENCES, CHAINS, SEGMENTS, STATUSES
from agencyrail.rail import Rail

STATIC_DIR = Path(__file__).resolve().parent / "static"

_rail: Rail | None = None

app = FastAPI(title="AgencyRail Desk", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_rail() -> Rail:
    global _rail
    if _rail is None:
        _rail = Rail()
    return _rail


def reset_rail(home: Path | None = None) -> Rail:
    global _rail
    if _rail is not None:
        _rail.close()
    _rail = Rail(home=home) if home is not None else None
    return get_rail()


class LeadIn(BaseModel):
    name: str
    org: str
    segment: str
    chain: str = "multi"
    email: Optional[str] = None
    telegram: Optional[str] = None
    twitter: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None


class LeadPatch(BaseModel):
    name: Optional[str] = None
    org: Optional[str] = None
    segment: Optional[str] = None
    chain: Optional[str] = None
    email: Optional[str] = None
    telegram: Optional[str] = None
    twitter: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    retainer: Optional[str] = None
    retainer_cadence: Optional[str] = None


class MoveIn(BaseModel):
    status: str


class InvoiceIn(BaseModel):
    amount: Optional[str] = None


class DigestIn(BaseModel):
    send: bool = Field(default=False)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"ok": "agencyrail"}


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    rail = get_rail()
    data = rail.meta()
    data["statuses"] = list(STATUSES)
    data["segments"] = list(SEGMENTS)
    data["chains"] = list(CHAINS)
    data["cadences"] = list(CADENCES)
    data["kinds"] = list(ARTIFACT_KINDS)
    return data


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    return get_rail().overview()


@app.get("/api/leads")
def list_leads(status: Optional[str] = None, segment: Optional[str] = None) -> list[dict[str, Any]]:
    try:
        return [lead.to_dict() for lead in get_rail().list_leads(status=status, segment=segment)]
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/leads")
def create_lead(body: LeadIn) -> dict[str, Any]:
    try:
        lead = get_rail().add_lead(**body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return lead.to_dict()


@app.get("/api/leads/{slug}")
def show_lead(slug: str) -> dict[str, Any]:
    rail = get_rail()
    try:
        lead = rail.get_lead(slug)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    artifacts = [item.to_dict() for item in rail.list_artifacts(lead.slug)]
    invoices = [inv.to_dict() for inv in rail.list_invoices(lead_id=lead.id)]
    events = [event.to_dict() for event in rail.store.list_events(limit=20, lead_id=lead.id)]
    return {"lead": lead.to_dict(), "artifacts": artifacts, "invoices": invoices, "events": events}


@app.patch("/api/leads/{slug}")
def patch_lead(slug: str, body: LeadPatch) -> dict[str, Any]:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        lead = get_rail().update_lead(slug, **fields)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return lead.to_dict()


@app.post("/api/leads/{slug}/move")
def move_lead(slug: str, body: MoveIn) -> dict[str, Any]:
    try:
        lead = get_rail().move_lead(slug, body.status)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return lead.to_dict()


@app.post("/api/leads/{slug}/run/{kind}")
def run_agent(slug: str, kind: str) -> dict[str, Any]:
    rail = get_rail()
    try:
        if kind == "pack":
            lead, artifacts = rail.run_pack(slug)
            return {"lead": lead.to_dict(), "artifacts": [item.to_dict() for item in artifacts]}
        lead, artifact = rail.run_agent(slug, kind)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"lead": lead.to_dict(), "artifact": artifact.to_dict()}


@app.post("/api/leads/{slug}/invoices")
def create_invoice(slug: str, body: InvoiceIn | None = None) -> dict[str, Any]:
    amount = body.amount if body else None
    try:
        invoice, path = get_rail().invoice(slug, amount=amount)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    data = invoice.to_dict()
    data["path"] = str(path)
    return data


@app.get("/api/invoices")
def list_invoices() -> list[dict[str, Any]]:
    rail = get_rail()
    out = []
    for invoice in rail.list_invoices():
        data = invoice.to_dict()
        data["org"] = rail.store.get_lead(invoice.lead_id).org
        out.append(data)
    return out


@app.post("/api/invoices/{number}/send")
def send_invoice(number: str) -> dict[str, Any]:
    try:
        return get_rail().send_invoice(number).to_dict()
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/invoices/{number}/pay")
def pay_invoice(number: str) -> dict[str, Any]:
    try:
        return get_rail().pay_invoice(number).to_dict()
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/digest")
def preview_digest() -> dict[str, Any]:
    digest = get_rail().digest(send=False)
    return {
        "week_of": digest.week_of,
        "markdown": digest.markdown,
        "telegram_text": digest.telegram_text,
        "path": str(digest.path) if digest.path else None,
        "dry_run": digest.dry_run,
        "sent": digest.sent,
    }


@app.post("/api/digest")
def post_digest(body: DigestIn) -> dict[str, Any]:
    try:
        digest = get_rail().digest(send=body.send)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "week_of": digest.week_of,
        "markdown": digest.markdown,
        "telegram_text": digest.telegram_text,
        "path": str(digest.path) if digest.path else None,
        "dry_run": digest.dry_run,
        "sent": digest.sent,
    }


@app.post("/api/seed")
def seed(force: bool = False) -> dict[str, Any]:
    slugs = get_rail().seed(force=force)
    return {"slugs": slugs}
