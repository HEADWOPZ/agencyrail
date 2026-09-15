from __future__ import annotations

import pytest

from agencyrail.models import parse_amount_to_cents
from agencyrail.store import slugify


def test_add_and_list_leads(rail):
    lead = rail.add_lead(
        name="Ava Chen",
        org="Helios Wallet",
        segment="wallet",
        chain="solana",
        email="ava@helioswallet.dev",
        website="https://helioswallet.dev",
    )
    assert lead.slug == "helios-wallet"
    assert lead.status == "intake"
    assert lead.next_action == "Run a visibility audit"
    listed = rail.list_leads()
    assert [item.slug for item in listed] == ["helios-wallet"]


def test_rejects_bad_segment(rail):
    with pytest.raises(ValueError, match="segment"):
        rail.add_lead(name="x", org="y", segment="exchange")


def test_move_and_retain(rail):
    rail.add_lead(name="Eli", org="Vaultkeep", segment="wallet")
    moved = rail.move_lead("vaultkeep", "negotiation")
    assert moved.status == "negotiation"
    retained = rail.retain("vaultkeep", "6000", cadence="monthly")
    assert retained.status == "retainer"
    assert retained.retainer_cents == 600000
    assert retained.retainer_cadence == "monthly"


def test_seed_is_idempotent(rail):
    first = rail.seed()
    second = rail.seed()
    assert len(first) == 6
    assert second == []
    assert len(rail.list_leads()) == 6


def test_seed_force_appends(rail):
    rail.seed()
    extra = rail.seed(force=True)
    assert extra
    assert len(rail.list_leads()) == 12


def test_slugify_and_amounts():
    assert slugify("Nimbus Swap") == "nimbus-swap"
    assert parse_amount_to_cents("4,500") == 450000
    assert parse_amount_to_cents(75) == 7500
    assert parse_amount_to_cents(99.5) == 9950


def test_filter_by_status_and_segment(seeded):
    wallets = seeded.list_leads(segment="wallet")
    assert {lead.org for lead in wallets} == {"Helios Wallet", "Vaultkeep"}
    retainers = seeded.list_leads(status="retainer")
    assert [lead.org for lead in retainers] == ["Vaultkeep"]
