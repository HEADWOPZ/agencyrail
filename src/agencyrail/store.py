from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from agencyrail.db import connect, init_db
from agencyrail.models import (
    CADENCES,
    CHAINS,
    INVOICE_STATUSES,
    NEXT_ACTION_BY_STATUS,
    SEGMENTS,
    STATUSES,
    Artifact,
    Event,
    Invoice,
    Lead,
    station_index,
)


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    out = []
    prev_dash = False
    for char in value.lower().strip():
        if char.isalnum():
            out.append(char)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-") or "lead"


def _require(value: str, allowed: Iterable[str], label: str) -> str:
    if value not in allowed:
        raise ValueError(f"{label} must be one of: {', '.join(allowed)}")
    return value


class Store:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = init_db(db_path)

    def close(self) -> None:
        self.conn.close()

    def reconnect(self) -> None:
        self.conn.close()
        self.conn = connect(self.db_path)

    # --- leads ---

    def add_lead(
        self,
        *,
        name: str,
        org: str,
        segment: str,
        chain: str = "multi",
        email: str | None = None,
        telegram: str | None = None,
        twitter: str | None = None,
        website: str | None = None,
        status: str = "intake",
        retainer_cents: int | None = None,
        retainer_cadence: str = "monthly",
        currency: str = "USD",
        notes: str | None = None,
        slug: str | None = None,
    ) -> Lead:
        _require(segment, SEGMENTS, "segment")
        _require(chain, CHAINS, "chain")
        _require(status, STATUSES, "status")
        _require(retainer_cadence, CADENCES, "retainer_cadence")
        now = utcnow()
        base = slugify(slug or org)
        final_slug = self._unique_slug(base)
        cur = self.conn.execute(
            """
            INSERT INTO leads (
                slug, name, org, segment, chain, email, telegram, twitter, website,
                status, retainer_cents, retainer_cadence, currency, score, next_action,
                notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
            """,
            (
                final_slug,
                name.strip(),
                org.strip(),
                segment,
                chain,
                _blank(email),
                _blank(telegram),
                _blank(twitter),
                _blank(website),
                status,
                retainer_cents,
                retainer_cadence,
                currency,
                NEXT_ACTION_BY_STATUS[status],
                _blank(notes),
                now,
                now,
            ),
        )
        self.conn.commit()
        lead = self.get_lead(cur.lastrowid)
        self.add_event(lead.id, "lead.created", f"Intake opened for {lead.org}")
        return lead

    def _unique_slug(self, base: str) -> str:
        slug = base
        n = 2
        while self.find_lead(slug):
            slug = f"{base}-{n}"
            n += 1
        return slug

    def get_lead(self, lead_id: int) -> Lead:
        row = self.conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not row:
            raise KeyError(f"lead {lead_id} not found")
        return _lead(row)

    def find_lead(self, slug_or_id: str | int) -> Lead | None:
        if isinstance(slug_or_id, int) or (isinstance(slug_or_id, str) and slug_or_id.isdigit()):
            row = self.conn.execute(
                "SELECT * FROM leads WHERE id = ? OR slug = ?",
                (int(slug_or_id), str(slug_or_id)),
            ).fetchone()
        else:
            row = self.conn.execute("SELECT * FROM leads WHERE slug = ?", (slug_or_id,)).fetchone()
        return _lead(row) if row else None

    def require_lead(self, slug_or_id: str | int) -> Lead:
        lead = self.find_lead(slug_or_id)
        if not lead:
            raise KeyError(f"lead '{slug_or_id}' not found")
        return lead

    def list_leads(self, status: str | None = None, segment: str | None = None) -> list[Lead]:
        sql = "SELECT * FROM leads"
        params: list[Any] = []
        clauses = []
        if status:
            _require(status, STATUSES, "status")
            clauses.append("status = ?")
            params.append(status)
        if segment:
            _require(segment, SEGMENTS, "segment")
            clauses.append("segment = ?")
            params.append(segment)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY CASE status"
        for i, station in enumerate(
            ("retainer", "negotiation", "outreach", "mockup", "audit", "intake", "closed", "lost")
        ):
            sql += f" WHEN '{station}' THEN {i}"
        sql += " END, updated_at DESC"
        return [_lead(row) for row in self.conn.execute(sql, params)]

    def update_lead(self, slug_or_id: str | int, **fields: Any) -> Lead:
        lead = self.require_lead(slug_or_id)
        allowed = {
            "name",
            "org",
            "segment",
            "chain",
            "email",
            "telegram",
            "twitter",
            "website",
            "status",
            "retainer_cents",
            "retainer_cadence",
            "currency",
            "score",
            "next_action",
            "notes",
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "status" in updates:
            _require(updates["status"], STATUSES, "status")
            updates.setdefault("next_action", NEXT_ACTION_BY_STATUS[updates["status"]])
        if "segment" in updates:
            _require(updates["segment"], SEGMENTS, "segment")
        if "chain" in updates:
            _require(updates["chain"], CHAINS, "chain")
        if "retainer_cadence" in updates:
            _require(updates["retainer_cadence"], CADENCES, "retainer_cadence")
        if not updates:
            return lead
        updates["updated_at"] = utcnow()
        assignments = ", ".join(f"{k} = ?" for k in updates)
        self.conn.execute(
            f"UPDATE leads SET {assignments} WHERE id = ?",
            (*updates.values(), lead.id),
        )
        self.conn.commit()
        return self.get_lead(lead.id)

    def move_lead(self, slug_or_id: str | int, status: str) -> Lead:
        before = self.require_lead(slug_or_id)
        lead = self.update_lead(slug_or_id, status=status)
        if before.status != lead.status:
            self.add_event(lead.id, "lead.moved", f"{before.status} → {lead.status}")
        return lead

    def advance_toward(self, slug_or_id: str | int, target: str) -> Lead:
        lead = self.require_lead(slug_or_id)
        if lead.status in {"closed", "lost", "retainer"}:
            return lead
        if station_index(lead.status) < station_index(target):
            return self.move_lead(lead.slug, target)
        return lead

    def counts_by_status(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM leads GROUP BY status"
        ).fetchall()
        counts = {status: 0 for status in STATUSES}
        for row in rows:
            counts[row["status"]] = row["n"]
        return counts

    # --- artifacts ---

    def add_artifact(
        self,
        lead_id: int,
        kind: str,
        title: str,
        body: str,
        meta_json: str | None = None,
    ) -> Artifact:
        now = utcnow()
        cur = self.conn.execute(
            """
            INSERT INTO artifacts (lead_id, kind, title, body, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (lead_id, kind, title, body, meta_json, now),
        )
        self.conn.commit()
        return self.get_artifact(cur.lastrowid)

    def get_artifact(self, artifact_id: int) -> Artifact:
        row = self.conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        if not row:
            raise KeyError(f"artifact {artifact_id} not found")
        return _artifact(row)

    def list_artifacts(self, lead_id: int | None = None, kind: str | None = None) -> list[Artifact]:
        sql = "SELECT * FROM artifacts"
        params: list[Any] = []
        clauses = []
        if lead_id is not None:
            clauses.append("lead_id = ?")
            params.append(lead_id)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC, id DESC"
        return [_artifact(row) for row in self.conn.execute(sql, params)]

    def latest_artifact(self, lead_id: int, kind: str) -> Artifact | None:
        row = self.conn.execute(
            """
            SELECT * FROM artifacts
            WHERE lead_id = ? AND kind = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (lead_id, kind),
        ).fetchone()
        return _artifact(row) if row else None

    # --- invoices ---

    def next_invoice_number(self, prefix: str, year: int) -> str:
        like = f"{prefix}-{year}-%"
        row = self.conn.execute(
            "SELECT number FROM invoices WHERE number LIKE ? ORDER BY number DESC LIMIT 1",
            (like,),
        ).fetchone()
        if not row:
            return f"{prefix}-{year}-0001"
        seq = int(row["number"].rsplit("-", 1)[-1]) + 1
        return f"{prefix}-{year}-{seq:04d}"

    def add_invoice(
        self,
        *,
        number: str,
        lead_id: int,
        amount_cents: int,
        currency: str,
        status: str,
        due_on: str,
        stripe_url: str | None,
        markdown: str,
    ) -> Invoice:
        _require(status, INVOICE_STATUSES, "status")
        now = utcnow()
        cur = self.conn.execute(
            """
            INSERT INTO invoices (
                number, lead_id, amount_cents, currency, status, due_on, stripe_url, markdown, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (number, lead_id, amount_cents, currency, status, due_on, stripe_url, markdown, now),
        )
        self.conn.commit()
        return self.get_invoice_by_id(cur.lastrowid)

    def get_invoice_by_id(self, invoice_id: int) -> Invoice:
        row = self.conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not row:
            raise KeyError(f"invoice {invoice_id} not found")
        return _invoice(row)

    def find_invoice(self, number: str) -> Invoice | None:
        row = self.conn.execute("SELECT * FROM invoices WHERE number = ?", (number,)).fetchone()
        return _invoice(row) if row else None

    def require_invoice(self, number: str) -> Invoice:
        invoice = self.find_invoice(number)
        if not invoice:
            raise KeyError(f"invoice '{number}' not found")
        return invoice

    def list_invoices(self, lead_id: int | None = None, status: str | None = None) -> list[Invoice]:
        sql = "SELECT * FROM invoices"
        params: list[Any] = []
        clauses = []
        if lead_id is not None:
            clauses.append("lead_id = ?")
            params.append(lead_id)
        if status:
            _require(status, INVOICE_STATUSES, "status")
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC"
        return [_invoice(row) for row in self.conn.execute(sql, params)]

    def set_invoice_status(self, number: str, status: str) -> Invoice:
        _require(status, INVOICE_STATUSES, "status")
        invoice = self.require_invoice(number)
        self.conn.execute("UPDATE invoices SET status = ? WHERE id = ?", (status, invoice.id))
        self.conn.commit()
        return self.require_invoice(number)

    # --- events ---

    def add_event(self, lead_id: int | None, kind: str, message: str) -> Event:
        now = utcnow()
        cur = self.conn.execute(
            "INSERT INTO events (lead_id, kind, message, created_at) VALUES (?, ?, ?, ?)",
            (lead_id, kind, message, now),
        )
        self.conn.commit()
        return _event(
            self.conn.execute("SELECT * FROM events WHERE id = ?", (cur.lastrowid,)).fetchone()
        )

    def list_events(self, limit: int = 40, lead_id: int | None = None) -> list[Event]:
        if lead_id is None:
            rows = self.conn.execute(
                "SELECT * FROM events ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            )
        else:
            rows = self.conn.execute(
                "SELECT * FROM events WHERE lead_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (lead_id, limit),
            )
        return [_event(row) for row in rows]


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _lead(row) -> Lead:
    return Lead(
        id=row["id"],
        slug=row["slug"],
        name=row["name"],
        org=row["org"],
        segment=row["segment"],
        chain=row["chain"],
        email=row["email"],
        telegram=row["telegram"],
        twitter=row["twitter"],
        website=row["website"],
        status=row["status"],
        retainer_cents=row["retainer_cents"],
        retainer_cadence=row["retainer_cadence"],
        currency=row["currency"],
        score=row["score"],
        next_action=row["next_action"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _artifact(row) -> Artifact:
    return Artifact(
        id=row["id"],
        lead_id=row["lead_id"],
        kind=row["kind"],
        title=row["title"],
        body=row["body"],
        meta_json=row["meta_json"],
        created_at=row["created_at"],
    )


def _invoice(row) -> Invoice:
    return Invoice(
        id=row["id"],
        number=row["number"],
        lead_id=row["lead_id"],
        amount_cents=row["amount_cents"],
        currency=row["currency"],
        status=row["status"],
        due_on=row["due_on"],
        stripe_url=row["stripe_url"],
        markdown=row["markdown"],
        created_at=row["created_at"],
    )


def _event(row) -> Event:
    return Event(
        id=row["id"],
        lead_id=row["lead_id"],
        kind=row["kind"],
        message=row["message"],
        created_at=row["created_at"],
    )
