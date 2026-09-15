from __future__ import annotations


def test_health_and_meta(desk):
    health = desk.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ok"] == "agencyrail"
    meta = desk.get("/api/meta")
    assert meta.status_code == 200
    assert meta.json()["operator"]["name"] == "Kevin Lance Murray"
    assert meta.json()["agency"]["name"] == "AgencyRail"


def test_index_is_dark_desk(desk):
    page = desk.get("/")
    assert page.status_code == 200
    assert "AgencyRail desk" in page.text
    assert "/static/app.js" in page.text


def test_lead_run_invoice_digest_api(desk):
    created = desk.post(
        "/api/leads",
        json={
            "name": "Jonah Park",
            "org": "Nimbus Swap",
            "segment": "dapp",
            "chain": "evm",
            "website": "https://nimbusswap.app",
        },
    )
    assert created.status_code == 200
    slug = created.json()["slug"]

    audit = desk.post(f"/api/leads/{slug}/run/audit")
    assert audit.status_code == 200
    assert audit.json()["lead"]["score"] is not None
    assert audit.json()["artifact"]["kind"] == "audit"

    invoice = desk.post(f"/api/leads/{slug}/invoices", json={})
    assert invoice.status_code == 200
    assert invoice.json()["stripe_url"].startswith("https://checkout.stripe.com/")

    digest = desk.get("/api/digest")
    assert digest.status_code == 200
    assert digest.json()["dry_run"] is True
    assert "Nimbus Swap" in digest.json()["telegram_text"]

    overview = desk.get("/api/overview")
    assert overview.status_code == 200
    assert overview.json()["counts"]["audit"] >= 1


def test_bad_segment_rejected(desk):
    response = desk.post(
        "/api/leads",
        json={"name": "x", "org": "y", "segment": "cex", "chain": "evm"},
    )
    assert response.status_code == 400
