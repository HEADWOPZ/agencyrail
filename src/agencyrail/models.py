from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

STATUSES = (
    "intake",
    "audit",
    "mockup",
    "outreach",
    "negotiation",
    "retainer",
    "closed",
    "lost",
)

SEGMENTS = ("protocol", "wallet", "dapp", "docs")
CHAINS = ("solana", "evm", "bitcoin", "sui", "multi")
ARTIFACT_KINDS = ("audit", "mockup", "outreach", "loom")
INVOICE_STATUSES = ("draft", "sent", "paid", "void")
CADENCES = ("monthly", "quarterly")

STATION_ORDER = (
    "intake",
    "audit",
    "mockup",
    "outreach",
    "negotiation",
    "retainer",
)

NEXT_ACTION_BY_STATUS = {
    "intake": "Run a visibility audit",
    "audit": "Turn findings into a mockup brief",
    "mockup": "Write outreach + Loom script",
    "outreach": "Send the note and book the call",
    "negotiation": "Lock scope and issue the retainer invoice",
    "retainer": "Deliver the weekly cycle; keep the digest honest",
    "closed": "Archive and ask for a referral",
    "lost": "Log why, then move on",
}


def station_index(status: str) -> int:
    try:
        return STATION_ORDER.index(status)
    except ValueError:
        return -1


@dataclass
class Lead:
    id: int
    slug: str
    name: str
    org: str
    segment: str
    chain: str
    email: str | None
    telegram: str | None
    twitter: str | None
    website: str | None
    status: str
    retainer_cents: int | None
    retainer_cadence: str
    currency: str
    score: int | None
    next_action: str | None
    notes: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["retainer"] = cents_to_amount(self.retainer_cents) if self.retainer_cents else None
        return data


@dataclass
class Artifact:
    id: int
    lead_id: int
    kind: str
    title: str
    body: str
    meta_json: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Invoice:
    id: int
    number: str
    lead_id: int
    amount_cents: int
    currency: str
    status: str
    due_on: str
    stripe_url: str | None
    markdown: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["amount"] = cents_to_amount(self.amount_cents)
        return data


@dataclass
class Event:
    id: int
    lead_id: int | None
    kind: str
    message: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Finding:
    severity: str
    title: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class AuditResult:
    score: int
    headline: str
    findings: list[Finding] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    recommended_retainer_cents: int = 450000


def cents_to_amount(cents: int) -> str:
    return f"{cents / 100:.2f}"


def parse_amount_to_cents(value: str | int | float) -> int:
    if isinstance(value, bool):
        raise ValueError("amount is required")
    if isinstance(value, int):
        return value * 100
    if isinstance(value, float):
        return int(round(value * 100))
    raw = str(value).strip().replace("$", "").replace(",", "")
    if not raw:
        raise ValueError("amount is required")
    return int(round(float(raw) * 100))
