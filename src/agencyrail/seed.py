from __future__ import annotations

from agencyrail.store import Store

SEED_LEADS = (
    {
        "name": "Ava Chen",
        "org": "Helios Wallet",
        "segment": "wallet",
        "chain": "solana",
        "email": "ava@helioswallet.dev",
        "telegram": "@avahelios",
        "twitter": "@helioswallet",
        "website": "https://helioswallet.dev",
        "status": "intake",
        "notes": "Extension + mobile. Weak first-session copy. Phantom-adjacent audience.",
    },
    {
        "name": "Marcus Adeyemi",
        "org": "Driftline Protocol",
        "segment": "protocol",
        "chain": "solana",
        "email": "marcus@driftline.xyz",
        "telegram": "@driftmarcus",
        "twitter": "@driftlinexyz",
        "website": "https://driftline.xyz",
        "status": "audit",
        "notes": "Perps protocol. Integrator docs are a GitBook dump.",
        "score": 58,
        "retainer_cents": 750000,
    },
    {
        "name": "Sofia Ruiz",
        "org": "Orbital Docs",
        "segment": "docs",
        "chain": "evm",
        "email": "sofia@orbitaldocs.io",
        "telegram": "@sofiaruiz",
        "twitter": "@orbitaldocs",
        "website": "https://docs.orbital.l2",
        "status": "mockup",
        "notes": "L2 docs portal. Quickstart is 14 pages. Wants a jobs-to-be-done IA.",
        "score": 61,
        "retainer_cents": 450000,
    },
    {
        "name": "Jonah Park",
        "org": "Nimbus Swap",
        "segment": "dapp",
        "chain": "evm",
        "email": "jonah@nimbusswap.app",
        "telegram": "@nimbusjonah",
        "twitter": "@nimbusswap",
        "website": "https://nimbusswap.app",
        "status": "outreach",
        "notes": "Connect CTA is 'Launch app'. No wrong-network state.",
        "score": 49,
        "retainer_cents": 500000,
    },
    {
        "name": "Priya Raman",
        "org": "Paperfold SDK",
        "segment": "docs",
        "chain": "multi",
        "email": "priya@paperfold.dev",
        "telegram": "@priyafold",
        "twitter": "@paperfoldsdk",
        "website": "https://paperfold.dev/docs",
        "status": "negotiation",
        "notes": "Wallet adapter docs. Samples look generated. Asking for a monthly rewrite.",
        "score": 67,
        "retainer_cents": 450000,
    },
    {
        "name": "Eli Navarro",
        "org": "Vaultkeep",
        "segment": "wallet",
        "chain": "multi",
        "email": "eli@vaultkeep.io",
        "telegram": "@elivault",
        "twitter": "@vaultkeep",
        "website": "https://vaultkeep.io",
        "status": "retainer",
        "notes": "Self-custody with inherited accounts. Paying for weekly trust + docs cycles.",
        "score": 74,
        "retainer_cents": 600000,
    },
)


def seed_demo(store: Store, force: bool = False) -> list[str]:
    existing = store.list_leads()
    if existing and not force:
        return []
    created = []
    for spec in SEED_LEADS:
        payload = dict(spec)
        score = payload.pop("score", None)
        lead = store.add_lead(**payload)
        if score is not None:
            store.update_lead(lead.slug, score=score)
        created.append(lead.slug)
    return created
