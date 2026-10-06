"""Correctness checks against hand-built briefs. No API calls."""

import json

from evals.scorers import correctness
from lead_brief import config, data_store
from lead_brief.schema import Brief

CASE = json.loads(config.ANSWER_KEY_PATH.read_text())[0]
KNOWN = data_store.all_source_ids()

GOOD = {
    "alert_level": "caution",
    "relationship_status": "at_risk_department",
    "related_account_ids": ["ACC-001", "ACC-002"],
    "headline": "h",
    "flags": [
        {"type": "renewal_risk", "claim": "c", "source_ids": ["usage:ACC-002"]},
        {"type": "champion_change", "claim": "c", "source_ids": ["transcript:T-0003", "crm:contact/CON-010"]},
    ],
    "summary": "s",
    "call_context_note": "n",
    "recommended_action": "a",
}


def results(**changes):
    checks = correctness(Brief.model_validate({**GOOD, **changes}), CASE, KNOWN)
    return {c.name: c.passed for c in checks}


def test_matching_brief_passes_all_six():
    assert results() == {
        "relationship_status": True,
        "alert_level": True,
        "related_accounts": True,
        "required_flags": True,
        "forbidden_flags": True,
        "source_ids_exist": True,
    }


def test_wrong_status_and_level_fail():
    r = results(relationship_status="healthy_department", alert_level="heads_up")
    assert not r["relationship_status"] and not r["alert_level"]


def test_lookalike_account_fails_related_accounts():
    assert not results(related_account_ids=["ACC-001", "ACC-002", "ACC-003"])["related_accounts"]
    assert not results(related_account_ids=["ACC-002"])["related_accounts"]


def test_required_flag_missing_or_wrongly_sourced_fails():
    only_renewal = [GOOD["flags"][0]]
    assert not results(flags=only_renewal)["required_flags"]
    wrong_source = [GOOD["flags"][0], {"type": "champion_change", "claim": "c", "source_ids": ["crm:opp/OPP-004"]}]
    assert not results(flags=wrong_source)["required_flags"]


def test_forbidden_flag_type_fails():
    extra = [*GOOD["flags"], {"type": "warm_reference", "claim": "c", "source_ids": ["crm:contact/CON-010"]}]
    assert not results(flags=extra)["forbidden_flags"]


def test_unknown_source_id_fails():
    extra = [*GOOD["flags"], {"type": "stale_contact", "claim": "c", "source_ids": ["crm:contact/CON-999"]}]
    assert not results(flags=extra)["source_ids_exist"]
