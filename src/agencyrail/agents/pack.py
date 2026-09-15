from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agencyrail.config import AppConfig
from agencyrail.models import ARTIFACT_KINDS, AuditResult, Finding, Lead, cents_to_amount
from agencyrail.store import Store

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

KIND_STATION = {
    "audit": "audit",
    "mockup": "mockup",
    "outreach": "outreach",
    "loom": "outreach",
}

KIND_TITLE = {
    "audit": "Visibility audit",
    "mockup": "Mockup brief",
    "outreach": "Cold outreach",
    "loom": "Loom script",
}


class AgentPack:
    """Deterministic operator agents. They grind so the closer can talk."""

    def __init__(self, store: Store, config: AppConfig):
        self.store = store
        self.config = config
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(disabled_extensions=("j2", "md")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def run(self, lead: Lead, kind: str) -> tuple[Lead, object]:
        if kind not in ARTIFACT_KINDS:
            raise ValueError(f"unknown agent '{kind}'")
        if kind == "audit":
            return self.run_audit(lead)
        if kind == "mockup":
            return self.run_mockup(lead)
        if kind == "outreach":
            return self.run_outreach(lead)
        return self.run_loom(lead)

    def run_all(self, lead: Lead) -> list[object]:
        artifacts = []
        current = lead
        for kind in ARTIFACT_KINDS:
            current, artifact = self.run(current, kind)
            artifacts.append(artifact)
        return artifacts

    def run_audit(self, lead: Lead):
        result = score_visibility(lead, self.config.agency.default_retainer_cents)
        body = self._render(
            "visibility_audit.md.j2",
            lead=lead,
            result=result,
            operator=self.config.operator,
            agency=self.config.agency,
            amount=cents_to_amount(result.recommended_retainer_cents),
        )
        artifact = self.store.add_artifact(
            lead.id,
            "audit",
            f"Visibility audit — {lead.org}",
            body,
            json.dumps({"score": result.score, "headline": result.headline}),
        )
        lead = self.store.update_lead(
            lead.slug,
            score=result.score,
            next_action="Turn findings into a mockup brief",
            retainer_cents=lead.retainer_cents or result.recommended_retainer_cents,
        )
        lead = self.store.advance_toward(lead.slug, "audit")
        self.store.add_event(lead.id, "agent.audit", f"Score {result.score} — {result.headline}")
        return lead, artifact

    def run_mockup(self, lead: Lead):
        screens = mockup_screens(lead)
        body = self._render(
            "mockup_brief.md.j2",
            lead=lead,
            operator=self.config.operator,
            agency=self.config.agency,
            screens=screens,
            offer=offer_line(lead),
        )
        artifact = self.store.add_artifact(
            lead.id,
            "mockup",
            f"Mockup brief — {lead.org}",
            body,
            json.dumps({"screens": [s["name"] for s in screens]}),
        )
        lead = self.store.update_lead(lead.slug, next_action="Write outreach + Loom script")
        lead = self.store.advance_toward(lead.slug, "mockup")
        self.store.add_event(lead.id, "agent.mockup", f"Briefed {len(screens)} screens")
        return lead, artifact

    def run_outreach(self, lead: Lead):
        subjects = subject_lines(lead)
        body = self._render(
            "outreach_email.md.j2",
            lead=lead,
            operator=self.config.operator,
            agency=self.config.agency,
            subjects=subjects,
            offer=offer_line(lead),
            hook=outreach_hook(lead),
        )
        artifact = self.store.add_artifact(
            lead.id,
            "outreach",
            f"Outreach — {lead.org}",
            body,
            json.dumps({"subjects": subjects}),
        )
        lead = self.store.update_lead(lead.slug, next_action="Send the note and book the call")
        lead = self.store.advance_toward(lead.slug, "outreach")
        self.store.add_event(lead.id, "agent.outreach", "Cold email drafted")
        return lead, artifact

    def run_loom(self, lead: Lead):
        beats = loom_beats(lead)
        body = self._render(
            "loom_script.md.j2",
            lead=lead,
            operator=self.config.operator,
            agency=self.config.agency,
            beats=beats,
            offer=offer_line(lead),
        )
        artifact = self.store.add_artifact(
            lead.id,
            "loom",
            f"Loom script — {lead.org}",
            body,
            json.dumps({"beats": [b["name"] for b in beats]}),
        )
        lead = self.store.update_lead(lead.slug, next_action="Record the Loom and send with the email")
        lead = self.store.advance_toward(lead.slug, "outreach")
        self.store.add_event(lead.id, "agent.loom", "90s walkthrough script ready")
        return lead, artifact

    def _render(self, name: str, **ctx) -> str:
        return self.env.get_template(name).render(**ctx).strip() + "\n"


def score_visibility(lead: Lead, default_retainer_cents: int) -> AuditResult:
    score = 38
    findings: list[Finding] = []
    strengths: list[str] = []

    if lead.website:
        score += 12
        strengths.append(f"Public surface exists ({lead.website}).")
    else:
        findings.append(
            Finding("high", "No public site on file", "Prospects cannot verify the product before a connect.")
        )

    if lead.twitter:
        score += 8
        strengths.append(f"X handle on file ({lead.twitter}).")
    else:
        findings.append(
            Finding("med", "X is missing", "Wallet and protocol buyers still check the timeline before they trust a CTA.")
        )

    if lead.telegram:
        score += 6
        strengths.append("Telegram path exists for the close.")
    else:
        findings.append(
            Finding("med", "No Telegram", "Crypto operators expect a short path to a human, not a Calendly maze.")
        )

    if lead.email:
        score += 4
    else:
        findings.append(Finding("low", "No email on file", "Add a founder or BD address before the send."))

    if lead.notes:
        score += 4
        strengths.append("Operator notes captured at intake.")

    findings.extend(segment_findings(lead))
    score += segment_bonus(lead)
    score = max(12, min(96, score))

    retainer = default_retainer_cents
    if lead.segment == "protocol":
        retainer = 750000
    elif lead.segment == "wallet":
        retainer = 600000
    elif lead.segment == "docs":
        retainer = 450000
    elif lead.segment == "dapp":
        retainer = 500000
    if score < 45:
        retainer += 100000

    headline = _headline(score, lead)
    return AuditResult(
        score=score,
        headline=headline,
        findings=findings,
        strengths=strengths,
        recommended_retainer_cents=retainer,
    )


def segment_bonus(lead: Lead) -> int:
    if lead.segment == "wallet" and lead.website:
        return 6
    if lead.segment == "docs" and lead.website:
        return 8
    if lead.segment == "protocol" and lead.twitter:
        return 5
    return 3


def segment_findings(lead: Lead) -> list[Finding]:
    chain = lead.chain
    if lead.segment == "wallet":
        return [
            Finding(
                "high",
                "Connect trust is underspecified",
                f"On {chain}, first-session trust is the product. Confirm network switch, account switch, and a rejected-tx state.",
            ),
            Finding(
                "high",
                "Recovery and phishing posture are invisible",
                "Buyers scan for seed-phrase warnings, deep-link hygiene, and a clear 'we never ask for your phrase' line.",
            ),
            Finding(
                "med",
                "Install-to-first-signature path is undocumented",
                "A 90-second 'connect this wallet' doc converts better than a feature grid.",
            ),
        ]
    if lead.segment == "dapp":
        return [
            Finding(
                "high",
                "Unsigned intent before connect",
                "Hero copy should say what the user is about to sign, on which chain, before the wallet modal opens.",
            ),
            Finding(
                "med",
                "Failed-tx and wallet-mismatch states missing",
                "Wrong network and user-rejected signatures are the two screens that keep support out of Telegram.",
            ),
            Finding(
                "med",
                "No proof of who built the dApp",
                "Add a docs/GitHub/X trail so Phantom-class users can sanity-check the origin.",
            ),
        ]
    if lead.segment == "protocol":
        return [
            Finding(
                "high",
                "Narrative is feature-first, not buyer-first",
                "Integrators need a one-screen 'why this chain/protocol this quarter' before token or TPS copy.",
            ),
            Finding(
                "med",
                "Docs IA is a dump, not a path",
                "Split quickstart, concepts, and reference. Hide the kitchen sink behind search.",
            ),
            Finding(
                "med",
                "Integration CTA is vague",
                "Name the next step: grant, Telegram, or a 20-minute integration review.",
            ),
        ]
    return [
        Finding(
            "high",
            "Quickstart is longer than a coffee",
            "Docs buyers bounce if 'hello world' is not copy-paste in under three minutes.",
        ),
        Finding(
            "med",
            "Nav is organized by repo, not by job",
            "Rewrite IA around Connect, Sign, Transfer, Troubleshoot — the jobs wallet/dApp teams actually have.",
        ),
        Finding(
            "low",
            "Code samples look generated",
            "Pin SDK versions and show a real error. Trust is in the details.",
        ),
    ]


def mockup_screens(lead: Lead) -> list[dict[str, str]]:
    if lead.segment == "wallet":
        return [
            {"name": "Landing / trust hero", "job": "Say who the wallet is for and what it never asks for."},
            {"name": "Connect modal", "job": f"First-session connect on {lead.chain} with network + account switch."},
            {"name": "Empty first-tx", "job": "Guide the first signature without dumping the user into a blank portfolio."},
            {"name": "Docs: connect in 90s", "job": "Install → connect → sign a harmless message."},
        ]
    if lead.segment == "dapp":
        return [
            {"name": "Product hero", "job": "Name the action and the chain before Connect."},
            {"name": "Wallet connect + wrong-network", "job": "Mismatch state with a one-click switch."},
            {"name": "Confirm intent", "job": "Human-readable summary of what will be signed."},
            {"name": "Receipt / share", "job": "Give the user a URL or tx they can show their group chat."},
        ]
    if lead.segment == "protocol":
        return [
            {"name": "Homepage narrative", "job": "One-screen why-now for integrators and funds."},
            {"name": "Docs hub", "job": "Quickstart / concepts / reference split."},
            {"name": "Integration CTA", "job": "Grant, Telegram, or review request — pick one primary."},
            {"name": "Ecosystem proof", "job": "Three real integrations, not a logo graveyard."},
        ]
    return [
        {"name": "Docs home", "job": "Search + four jobs-to-be-done, not a file tree."},
        {"name": "Quickstart", "job": "Copy-paste path to first success in <3 minutes."},
        {"name": "Recipe: connect + sign", "job": "Wallet/dApp-shaped example with pinned versions."},
        {"name": "Troubleshoot", "job": "Rejected tx, wrong network, stale RPC."},
    ]


def subject_lines(lead: Lead) -> list[str]:
    org = lead.org
    if lead.segment == "wallet":
        return [
            f"{org} — connect trust in 90 seconds",
            f"A mockup for {org}'s first session",
            f"Quick note on {org}'s install-to-signature path",
        ]
    if lead.segment == "dapp":
        return [
            f"{org}: the screen before Connect",
            f"Wrong-network is costing {org} users",
            f"Mocked a confirm-intent flow for {org}",
        ]
    if lead.segment == "protocol":
        return [
            f"{org} docs/narrative — integrator-first pass",
            f"Why {org} this quarter (one screen)",
            f"{org} — a 7-day mockup, not a rebrand",
        ]
    return [
        f"{org} quickstart is a coffee too long",
        f"Rewrite {org} docs around jobs, not repos",
        f"A 3-minute hello-world for {org}",
    ]


def outreach_hook(lead: Lead) -> str:
    if lead.segment == "wallet":
        return (
            f"I walked {lead.org}'s public surface the way a first-time {lead.chain} user would: "
            "install, connect, and look for a reason to trust the first signature."
        )
    if lead.segment == "dapp":
        return (
            f"I tried to use {lead.org} like a cautious wallet user — I wanted to know the chain, "
            "the intent, and what happens if I reject the signature."
        )
    if lead.segment == "protocol":
        return (
            f"I read {lead.org} as an integrator would this quarter: why you, why now, "
            "and where the first successful integration actually starts."
        )
    return (
        f"I timed {lead.org}'s hello-world the way a docs-tired wallet team would. "
        "The path is there — the job-to-be-done is not."
    )


def loom_beats(lead: Lead) -> list[dict[str, str]]:
    return [
        {"name": "Hook", "seconds": "0:00–0:08", "line": f"{lead.org} is leaking trust before the first signature."},
        {"name": "Problem", "seconds": "0:08–0:28", "line": outreach_hook(lead)},
        {"name": "Walkthrough", "seconds": "0:28–1:10", "line": f"Three screens I would ship for {lead.org} this week."},
        {"name": "Ask", "seconds": "1:10–1:30", "line": "12 minutes on Telegram. I already have the brief."},
    ]


def offer_line(lead: Lead) -> str:
    mapping = {
        "wallet": "Install-to-signature trust sprint (site + connect + 90s docs)",
        "dapp": "Connect / intent / mismatch sprint for the live dApp",
        "protocol": "Integrator narrative + docs IA sprint",
        "docs": "Jobs-to-be-done docs rewrite + quickstart",
    }
    return mapping[lead.segment]


def _headline(score: int, lead: Lead) -> str:
    if score >= 75:
        return f"{lead.org} is close — tighten the last-mile trust path."
    if score >= 55:
        return f"{lead.org} has a surface; the first session still leaks."
    return f"{lead.org} is invisible where wallet and dApp buyers decide."
