from __future__ import annotations

from agencyrail.billing.invoices import stub_checkout_url


def test_invoice_markdown_and_stripe_stub(rail):
    lead = rail.add_lead(
        name="Eli Navarro",
        org="Vaultkeep",
        segment="wallet",
        retainer_cents=600000,
    )
    invoice, path = rail.invoice(lead.slug)
    assert invoice.number.startswith("AR-")
    assert invoice.amount_cents == 600000
    assert invoice.status == "draft"
    assert invoice.stripe_url == stub_checkout_url(invoice.number)
    assert "stub_agencyrail" in invoice.stripe_url
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert invoice.number in text
    assert "Vaultkeep" in text
    assert "6000.00" in text


def test_invoice_amount_override_and_numbering(rail):
    lead = rail.add_lead(name="Ava", org="Helios Wallet", segment="wallet")
    first, _ = rail.invoice(lead.slug, amount="4500")
    second, _ = rail.invoice(lead.slug, amount="5000")
    assert first.amount_cents == 450000
    assert second.amount_cents == 500000
    assert first.number != second.number
    assert first.number.endswith("0001")
    assert second.number.endswith("0002")


def test_pay_moves_to_retainer(rail):
    lead = rail.add_lead(name="Jonah", org="Nimbus Swap", segment="dapp", status="outreach")
    invoice, _ = rail.invoice(lead.slug, amount="5000")
    rail.send_invoice(invoice.number)
    paid = rail.pay_invoice(invoice.number)
    assert paid.status == "paid"
    assert rail.get_lead(lead.slug).status == "retainer"
