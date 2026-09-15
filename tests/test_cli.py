from __future__ import annotations

from agencyrail.cli import app


def test_cli_init_seed_status(runner, home):
    result = runner.invoke(app, ["--home", str(home), "init"])
    assert result.exit_code == 0, result.output
    assert "Initialized" in result.output

    seeded = runner.invoke(app, ["--home", str(home), "seed"])
    assert seeded.exit_code == 0, seeded.output
    assert "helios-wallet" in seeded.output

    status = runner.invoke(app, ["--home", str(home), "status"])
    assert status.exit_code == 0, status.output
    assert "Vaultkeep" in status.output
    assert "RETAINER" in status.output


def test_cli_pipeline(runner, home):
    runner.invoke(app, ["--home", str(home), "init"])
    add = runner.invoke(
        app,
        [
            "--home",
            str(home),
            "lead",
            "add",
            "--name",
            "Ava Chen",
            "--org",
            "Helios Wallet",
            "--segment",
            "wallet",
            "--chain",
            "solana",
            "--website",
            "https://helioswallet.dev",
        ],
    )
    assert add.exit_code == 0, add.output

    pack = runner.invoke(app, ["--home", str(home), "run", "pack", "helios-wallet"])
    assert pack.exit_code == 0, pack.output
    assert "pack complete" in pack.output

    invoice = runner.invoke(app, ["--home", str(home), "invoice", "create", "helios-wallet"])
    assert invoice.exit_code == 0, invoice.output
    assert "AR-" in invoice.output
    assert "stripe stub" in invoice.output

    digest = runner.invoke(app, ["--home", str(home), "digest"])
    assert digest.exit_code == 0, digest.output
    assert "dry-run" in digest.output
    assert "Helios Wallet" in digest.output


def test_cli_help(runner):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "intake to retainer" in result.output.lower() or "AgencyRail" in result.output
