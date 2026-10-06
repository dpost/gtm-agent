"""Loads the synthetic data and implements the five read-only tool functions.

The same functions serve the agent loop and, later, the MCP server. Every record
returned carries a `source_id` the agent can cite.
"""

import json
from functools import lru_cache
from pathlib import Path

from lead_brief import config


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_transcript(path: Path) -> dict:
    header, body = path.read_text(encoding="utf-8").split("\n---\n", 1)
    meta = dict(line.split(": ", 1) for line in header.strip().splitlines())
    meta["contact_ids"] = [c.strip() for c in meta.get("contact_ids", "").split(",") if c.strip()]
    meta["text"] = body.strip()
    return meta


@lru_cache(maxsize=None)
def _load() -> dict:
    crm = config.DATA_DIR / "crm"
    raw = {
        "accounts": _read_json(crm / "accounts.json"),
        "contacts": _read_json(crm / "contacts.json"),
        "opps": _read_json(crm / "opportunities.json"),
        "leads": _read_json(crm / "leads.json"),
        "usage": [_read_json(p) for p in sorted((config.DATA_DIR / "usage").glob("*.json"))],
        "transcripts": [_parse_transcript(p) for p in sorted((config.DATA_DIR / "transcripts").glob("*.txt"))],
    }
    return {
        "raw": raw,
        "accounts": {a["account_id"]: a for a in raw["accounts"]},
        "contacts": {c["contact_id"]: c for c in raw["contacts"]},
        "opps": {o["opp_id"]: o for o in raw["opps"]},
        "leads": {lead["lead_id"]: lead for lead in raw["leads"]},
        "usage": {u["account_id"]: u for u in raw["usage"]},
        "transcripts": sorted(raw["transcripts"], key=lambda t: t["date"]),
    }


def _account_ref(account: dict) -> dict:
    return {
        "account_id": account["account_id"],
        "source_id": f"crm:account/{account['account_id']}",
        "name": account["name"],
        "name_variants": account["name_variants"],
    }


def _hierarchy(account: dict) -> dict:
    accounts = _load()["accounts"]
    parent = accounts.get(account["parent_account_id"]) if account["parent_account_id"] else None
    children = [a for a in accounts.values() if a["parent_account_id"] == account["account_id"]]
    return {
        "parent": _account_ref(parent) if parent else None,
        "children": [_account_ref(c) for c in children],
    }


# ---- The five tools ----


def search_accounts(name: str) -> dict:
    """Find accounts whose name or a name variant contains `name` (case-insensitive)."""
    query = name.strip().lower()
    matches = []
    if query:
        for account in _load()["accounts"].values():
            names = [account["name"], *account["name_variants"]]
            if any(query in n.lower() for n in names):
                matches.append({
                    **_account_ref(account),
                    "domain": account["domain"],
                    "is_customer": account["is_customer"],
                    **_hierarchy(account),
                })
    return {"query": name, "matches": matches}


def get_account(account_id: str) -> dict:
    """CRM record for one account, with hierarchy, contacts, opportunities (incl. MEDDPICC), and activity."""
    data = _load()
    account = data["accounts"].get(account_id)
    if account is None:
        return {"error": f"No account with ID {account_id}."}
    contacts = [
        {"source_id": f"crm:contact/{c['contact_id']}", **c}
        for c in data["contacts"].values()
        if c["account_id"] == account_id
    ]
    opps = [
        {"source_id": f"crm:opp/{o['opp_id']}", **o}
        for o in data["opps"].values()
        if o["account_id"] == account_id
    ]
    return {
        "source_id": f"crm:account/{account_id}",
        **account,
        **_hierarchy(account),
        "contacts": contacts,
        "opportunities": opps,
    }


def get_usage(account_id: str) -> dict:
    """The 12-week usage scorecard for a customer account."""
    data = _load()
    scorecard = data["usage"].get(account_id)
    if scorecard is None:
        if account_id in data["accounts"]:
            return {"account_id": account_id, "error": "No usage scorecard for this account."}
        return {"error": f"No account with ID {account_id}."}
    return {"source_id": f"usage:{account_id}", **scorecard}


def search_transcripts(query: str) -> dict:
    """Call transcripts matching an account ID or name, contact ID or name, or text (case-insensitive)."""
    data = _load()
    needle = query.strip().lower()
    hits = []
    if needle:
        for t in data["transcripts"]:
            account = data["accounts"].get(t["account_id"], {})
            haystack = " ".join([
                t["transcript_id"],
                t["account_id"],
                account.get("name", ""),
                *account.get("name_variants", []),
                t.get("participants", ""),
                *t["contact_ids"],
                t["text"],
            ]).lower()
            if needle in haystack:
                hits.append({
                    "source_id": f"transcript:{t['transcript_id']}",
                    "transcript_id": t["transcript_id"],
                    "account_id": t["account_id"],
                    "account_name": account.get("name"),
                    "date": t["date"],
                    "call_type": t.get("call_type"),
                    "participants": t.get("participants"),
                    "contact_ids": t["contact_ids"],
                    "text": t["text"],
                })
    return {"query": query, "hits": hits}


def find_person(name_or_email: str) -> dict:
    """Every contact record for a person, across accounts, matched by name substring or email."""
    data = _load()
    needle = name_or_email.strip().lower()
    matches = []
    if needle:
        for c in data["contacts"].values():
            if needle in c["name"].lower() or needle == c["email"].lower():
                account = data["accounts"].get(c["account_id"], {})
                matches.append({
                    "source_id": f"crm:contact/{c['contact_id']}",
                    **c,
                    "account_name": account.get("name"),
                })
    return {"query": name_or_email, "matches": matches}


# ---- Helpers for the agent and evals (not tools) ----


def get_lead(lead_id: str) -> dict:
    lead = _load()["leads"].get(lead_id)
    if lead is None:
        raise KeyError(f"No lead with ID {lead_id}.")
    return {"source_id": f"crm:lead/{lead_id}", **lead}


def all_record_ids() -> list[str]:
    """Every record ID in the data, duplicates included, for uniqueness checks."""
    raw = _load()["raw"]
    return (
        [a["account_id"] for a in raw["accounts"]]
        + [c["contact_id"] for c in raw["contacts"]]
        + [o["opp_id"] for o in raw["opps"]]
        + [lead["lead_id"] for lead in raw["leads"]]
        + [t["transcript_id"] for t in raw["transcripts"]]
    )


def all_source_ids() -> set[str]:
    """Every citable source ID in the data."""
    data = _load()
    return (
        {f"crm:account/{i}" for i in data["accounts"]}
        | {f"crm:contact/{i}" for i in data["contacts"]}
        | {f"crm:opp/{i}" for i in data["opps"]}
        | {f"crm:lead/{i}" for i in data["leads"]}
        | {f"usage:{i}" for i in data["usage"]}
        | {f"transcript:{t['transcript_id']}" for t in data["transcripts"]}
    )
