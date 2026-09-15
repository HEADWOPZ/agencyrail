from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OPERATOR_NAME = "Kevin Lance Murray"
DEFAULT_HANDLE = "HEADWOPZ"
DEFAULT_EMAIL = "kevin@agencyrail.io"
DEFAULT_TELEGRAM = "@headwopz"
DEFAULT_X = "@headwopz"


@dataclass(frozen=True)
class Operator:
    name: str
    handle: str
    email: str
    telegram: str
    x: str


@dataclass(frozen=True)
class Agency:
    name: str
    tagline: str
    default_retainer_cents: int
    currency: str
    invoice_prefix: str


@dataclass(frozen=True)
class Integrations:
    stripe_mode: str
    telegram_dry_run: bool
    telegram_bot_token: str | None
    telegram_chat_id: str | None


@dataclass(frozen=True)
class AppConfig:
    operator: Operator
    agency: Agency
    integrations: Integrations


def default_home() -> Path:
    env = os.environ.get("AGENCYRAIL_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.cwd() / ".agencyrail").resolve()


def default_config() -> AppConfig:
    return AppConfig(
        operator=Operator(
            name=os.environ.get("AGENCYRAIL_OPERATOR", DEFAULT_OPERATOR_NAME),
            handle=os.environ.get("AGENCYRAIL_HANDLE", DEFAULT_HANDLE),
            email=os.environ.get("AGENCYRAIL_EMAIL", DEFAULT_EMAIL),
            telegram=os.environ.get("AGENCYRAIL_TELEGRAM", DEFAULT_TELEGRAM),
            x=os.environ.get("AGENCYRAIL_X", DEFAULT_X),
        ),
        agency=Agency(
            name="AgencyRail",
            tagline="Crypto-native AI agency ops",
            default_retainer_cents=450000,
            currency="USD",
            invoice_prefix="AR",
        ),
        integrations=Integrations(
            stripe_mode="stub",
            telegram_dry_run=True,
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
        ),
    )


def write_example_config(home: Path) -> Path:
    path = home / "config.toml"
    if path.exists():
        return path
    path.write_text(
        """# AgencyRail operator config
# Values here are documentation; the CLI also reads AGENCYRAIL_* env vars.

[operator]
name = "Kevin Lance Murray"
handle = "HEADWOPZ"
email = "kevin@agencyrail.io"
telegram = "@headwopz"
x = "@headwopz"

[agency]
name = "AgencyRail"
tagline = "Crypto-native AI agency ops"
default_retainer_cents = 450000
currency = "USD"
invoice_prefix = "AR"

[integrations]
stripe_mode = "stub"
telegram_dry_run = true
""",
        encoding="utf-8",
    )
    return path
