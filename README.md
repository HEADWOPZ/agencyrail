# AgencyRail

Crypto-native AI agency ops kit for a solo operator.

**Kevin Lance Murray** runs protocols, wallets, dApps, and docs clients through one rail:

**intake → audit → mockup → outreach → retainer**

Agents do the grind. The desk keeps the close honest.

## What you get

1. **CRM-lite (SQLite)** — leads, rail status, retainer, artifacts, invoices, event log.
2. **Agent pack** — visibility audit, mockup brief, cold outreach, 90-second Loom script. Written for wallet / dApp / protocol / docs buyers, not generic SaaS.
3. **Invoice hooks** — markdown invoice plus a Stripe Checkout stub URL. Mark sent/paid; paid moves the lead to retainer.
4. **Weekly Telegram digest** — dry-run by default (markdown + console). `--send` posts when Telegram env vars exist.
5. **CLI + dark desk** — `agencyrail` in the terminal, `agencyrail desk` for the operator UI.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Quick start

```bash
agencyrail init
agencyrail seed
agencyrail status

agencyrail run pack helios-wallet
agencyrail invoice create vaultkeep
agencyrail digest
agencyrail desk
```

`agencyrail` with no arguments is the same as `agencyrail status`.

The desk lives at [http://127.0.0.1:8787](http://127.0.0.1:8787). First visit seeds the demo rail if the CRM is empty.

## The rail

| Station | What happens |
| --- | --- |
| `intake` | Capture org, segment, chain, surfaces, notes |
| `audit` | Score visibility; name the leaks |
| `mockup` | 7-day screen brief (not a rebrand) |
| `outreach` | Subject lines + email + Loom script |
| `negotiation` | Scope the retainer |
| `retainer` | Invoice paid; weekly cycle |
| `closed` / `lost` | Off the rail |

Segments: `wallet` · `dapp` · `protocol` · `docs`  
Chains: `solana` · `evm` · `bitcoin` · `sui` · `multi`

## CLI

```text
agencyrail init
agencyrail seed [--force]
agencyrail status

agencyrail lead add --name NAME --org ORG --segment wallet --chain solana
agencyrail lead list [--status outreach] [--segment dapp]
agencyrail lead show SLUG
agencyrail lead move SLUG negotiation
agencyrail lead retain SLUG --amount 6000

agencyrail run audit SLUG
agencyrail run mockup SLUG
agencyrail run outreach SLUG
agencyrail run loom SLUG
agencyrail run pack SLUG

agencyrail invoice create SLUG [--amount 4500]
agencyrail invoice list
agencyrail invoice send AR-2026-0001
agencyrail invoice pay AR-2026-0001

agencyrail digest            # dry-run
agencyrail digest --send     # Telegram, if configured
agencyrail desk --port 8787
```

`--home` / `AGENCYRAIL_HOME` points at the workspace (default: `./.agencyrail`).

## Agent pack

Templates live in `src/agencyrail/templates/`. The runners are deterministic on purpose: same lead in, same brief out, so you can edit and re-run.

| Agent | Output |
| --- | --- |
| Visibility audit | Score, findings, recommended retainer |
| Mockup brief | 4 screens, copy blocks, out of scope |
| Outreach email | 3 subjects + a short note from Kevin |
| Loom script | 90 seconds, shot list, spoken draft |

Wallet briefs talk connect trust, recovery, and install-to-signature. dApp briefs talk intent-before-connect and wrong-network. Protocol briefs talk integrator narrative. Docs briefs talk jobs-to-be-done and a three-minute quickstart.

## Billing

`agencyrail invoice create` writes:

- a row in SQLite
- `/.agencyrail/invoices/AR-YYYY-NNNN-<slug>.md`
- a stub Checkout URL: `https://checkout.stripe.com/c/pay/stub_agencyrail_...`

This is a stub so the rail works without Stripe keys. Swap the URL when you go live. `invoice pay` marks the invoice paid and moves the lead to `retainer`.

## Telegram digest

Dry-run (default) prints the message and writes `/.agencyrail/digests/weekly-YYYY-MM-DD.md`.

To send for real:

```bash
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
agencyrail digest --send
```

## Data

```text
.agencyrail/
  agencyrail.db
  config.toml          # operator identity (documented defaults)
  invoices/
  digests/
```

Operator defaults: Kevin Lance Murray / HEADWOPZ. Override with `AGENCYRAIL_OPERATOR`, `AGENCYRAIL_EMAIL`, `AGENCYRAIL_TELEGRAM`, `AGENCYRAIL_X`.

## Tests

```bash
pytest
```

## License

MIT © 2026 Kevin Lance Murray
