from __future__ import annotations

from agencyrail.agents.pack import score_visibility
from agencyrail.config import default_config


def test_audit_scores_and_stores_artifact(rail):
    lead = rail.add_lead(
        name="Jonah Park",
        org="Nimbus Swap",
        segment="dapp",
        chain="evm",
        website="https://nimbusswap.app",
        twitter="@nimbusswap",
        notes="Connect CTA is Launch app.",
    )
    lead, artifact = rail.run_agent(lead.slug, "audit")
    assert artifact.kind == "audit"
    assert "Visibility audit" in artifact.title
    assert "Nimbus Swap" in artifact.body
    assert lead.score is not None
    assert 40 <= lead.score <= 90
    assert lead.status == "audit"
    assert lead.retainer_cents == 500000


def test_pack_advances_to_outreach(rail):
    lead = rail.add_lead(name="Sofia Ruiz", org="Orbital Docs", segment="docs", chain="evm")
    lead, artifacts = rail.run_pack(lead.slug)
    assert [item.kind for item in artifacts] == ["audit", "mockup", "outreach", "loom"]
    assert lead.status == "outreach"
    assert "quickstart" in artifacts[1].body.lower()
    assert "Subject" in artifacts[2].body
    assert "90" in artifacts[3].body


def test_does_not_move_retainer_backwards(rail):
    lead = rail.add_lead(name="Eli", org="Vaultkeep", segment="wallet", status="retainer")
    lead, _ = rail.run_agent(lead.slug, "audit")
    assert lead.status == "retainer"


def test_score_penalizes_dark_lead():
    from agencyrail.models import Lead

    lead = Lead(
        id=1,
        slug="ghost",
        name="Ghost",
        org="Ghost Protocol",
        segment="protocol",
        chain="solana",
        email=None,
        telegram=None,
        twitter=None,
        website=None,
        status="intake",
        retainer_cents=None,
        retainer_cadence="monthly",
        currency="USD",
        score=None,
        next_action=None,
        notes=None,
        created_at="",
        updated_at="",
    )
    result = score_visibility(lead, 450000)
    assert result.score < 50
    assert result.recommended_retainer_cents >= 750000
    assert any(item.severity == "high" for item in result.findings)


def test_unknown_agent_rejected(rail):
    lead = rail.add_lead(name="A", org="B", segment="wallet")
    try:
        rail.run_agent(lead.slug, "rebrand")
        assert False, "should have raised"
    except ValueError as exc:
        assert "unknown" in str(exc)


def test_pack_mentions_operator(rail):
    config = default_config()
    lead = rail.add_lead(name="Priya Raman", org="Paperfold SDK", segment="docs")
    _, artifacts = rail.run_pack(lead.slug)
    assert any(config.operator.name in item.body for item in artifacts)
