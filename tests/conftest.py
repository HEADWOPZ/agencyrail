from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from agencyrail.desk.app import reset_rail
from agencyrail.rail import Rail


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AGENCYRAIL_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def rail(home: Path) -> Rail:
    instance = Rail(home=home)
    yield instance
    instance.close()


@pytest.fixture
def seeded(rail: Rail) -> Rail:
    rail.seed()
    return rail


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def desk(home: Path):
    reset_rail(home)
    from agencyrail.desk.app import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client
