"""Tool schemas for the Anthropic Messages API, mapped to the data_store functions."""

import json

from lead_brief import data_store


def _tool(name: str, description: str, param: str, param_description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {param: {"type": "string", "description": param_description}},
            "required": [param],
            "additionalProperties": False,
        },
    }


TOOLS = [
    _tool(
        "search_accounts",
        "Search CRM accounts by company name. Case-insensitive substring match against each account's "
        "name and known name variants. Returns each match with its domain, customer status, parent "
        "account, and child accounts.",
        "name",
        "Company name or part of one, e.g. 'Acme' or 'Acme Logistics'.",
    ),
    _tool(
        "get_account",
        "Get the full CRM record for one account: owner, ARR, seats, renewal date, parent and child "
        "accounts, contacts (role tags, employment history, last-updated date), opportunities (stage, "
        "owner, amount, close date, closed-lost reason, rep-entered MEDDPICC fields with last-updated "
        "dates), and activity notes.",
        "account_id",
        "Account ID, e.g. 'ACC-017'.",
    ),
    _tool(
        "get_usage",
        "Get the 12-week usage scorecard for a customer account: licensed seats, active seats, "
        "utilization, feature adoption counts, and health score for each week. Accounts that are not "
        "customers have no scorecard.",
        "account_id",
        "Account ID, e.g. 'ACC-017'.",
    ),
    _tool(
        "search_transcripts",
        "Search call transcripts by account ID, account name, contact ID, contact name, or a phrase. "
        "Case-insensitive substring match. Returns each hit's ID, account, date, participants, and full text.",
        "query",
        "An account ID, contact ID, name, or phrase, e.g. 'ACC-017' or 'Jordan Lee'.",
    ),
    _tool(
        "find_person",
        "Find every CRM contact record for a person across all accounts, by name (substring) or exact "
        "email. Shows whether someone is, or was, a contact at any account.",
        "name_or_email",
        "Full name, part of a name, or an email address.",
    ),
]

TOOL_FUNCTIONS = {
    "search_accounts": data_store.search_accounts,
    "get_account": data_store.get_account,
    "get_usage": data_store.get_usage,
    "search_transcripts": data_store.search_transcripts,
    "find_person": data_store.find_person,
}


def run_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Run one tool call. Returns (JSON result text, is_error)."""
    fn = TOOL_FUNCTIONS.get(name) or TOOL_FUNCTIONS.get(name.lower())
    if fn is None:
        return json.dumps({"error": f"Unknown tool '{name}'. Available: {sorted(TOOL_FUNCTIONS)}."}), True
    try:
        result = fn(**tool_input)
    except TypeError as e:
        return json.dumps({"error": f"Bad arguments for {name}: {e}"}), True
    return json.dumps(result, ensure_ascii=False), False
