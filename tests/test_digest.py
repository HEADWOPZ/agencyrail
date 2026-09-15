from __future__ import annotations

import httpx
import pytest


def test_weekly_digest_dry_run(seeded):
    seeded.run_agent("helios-wallet", "audit")
    seeded.invoice("vaultkeep")
    digest = seeded.digest(send=False)
    assert digest.dry_run is True
    assert digest.sent is False
    assert digest.path and digest.path.exists()
    assert "AgencyRail" in digest.telegram_text
    assert "Vaultkeep" in digest.telegram_text
    assert "Helios Wallet" in digest.markdown
    assert "Outstanding" in digest.markdown


def test_digest_send_requires_telegram_env(rail):
    with pytest.raises(RuntimeError, match="TELEGRAM"):
        rail.digest(send=True)


def test_send_telegram_posts(monkeypatch):
    from agencyrail.digest.telegram import send_telegram

    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))

        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"ok": True}

        return Resp()

    monkeypatch.setattr(httpx, "post", fake_post)
    result = send_telegram("hello rail", "token", "chat-1")
    assert result["ok"] is True
    assert calls[0][0] == "https://api.telegram.org/bottoken/sendMessage"
    assert calls[0][1]["chat_id"] == "chat-1"
