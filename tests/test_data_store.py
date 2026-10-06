"""Tool functions return the right records for L-001. No API calls."""

import json
from collections import Counter

from lead_brief import config, data_store as ds


def account_ids(result: dict) -> list[str]:
    return [m["account_id"] for m in result["matches"]]


# ---- Tool functions return the right records for L-001 ----


def test_lead_record():
    lead = ds.get_lead("L-001")
    assert lead["source_id"] == "crm:lead/L-001"
    assert lead["company"] == "Pellwick Freight"
    assert lead["email"] == "marcus.oyelaran@pellwickfreight.example"


def test_search_accounts_finds_the_family():
    assert account_ids(ds.search_accounts("Pellwick Freight")) == ["ACC-001", "ACC-002"]
    assert account_ids(ds.search_accounts("pwf marketing")) == ["ACC-002"]
    match = ds.search_accounts("Pellwick Freight")["matches"][0]
    assert [c["account_id"] for c in match["children"]] == ["ACC-002"]


def test_get_account_acc002_has_renewal_and_stale_meddpicc():
    account = ds.get_account("ACC-002")
    assert account["source_id"] == "crm:account/ACC-002"
    assert account["parent"]["account_id"] == "ACC-001"
    assert (account["account_owner"], account["arr_usd"], account["licensed_seats"]) == ("Riley Chen", 86000, 120)
    assert [c["source_id"] for c in account["contacts"]] == ["crm:contact/CON-010", "crm:contact/CON-011"]
    (opp,) = account["opportunities"]
    assert opp["source_id"] == "crm:opp/OPP-004"
    assert (opp["stage"], opp["owner"], opp["close_date"]) == ("Renewal: Negotiation", "Riley Chen", "2026-11-20")
    assert opp["meddpicc"]["champion"]["contact_id"] == "CON-010"
    assert opp["meddpicc"]["champion"]["last_updated"] == "2026-05-12"


def test_get_usage_acc002_slides_from_green_to_red():
    usage = ds.get_usage("ACC-002")
    weeks = usage["weeks"]
    assert usage["source_id"] == "usage:ACC-002"
    assert len(weeks) == 12 and weeks[-1]["week_ending"] == "2026-10-04"
    assert weeks[0]["utilization_pct"] == 80.0 and weeks[-1]["utilization_pct"] == 45.0
    assert weeks[0]["health_band"] == "green" and weeks[-1]["health_band"] == "red"
    drops = [a["active_seats"] - b["active_seats"] for a, b in zip(weeks, weeks[1:])]
    assert min(drops[-5:]) > max(drops[:-5])  # steepest decline in the last five weeks


def test_parent_account_has_no_usage():
    assert "error" in ds.get_usage("ACC-001")
    assert "error" in ds.get_usage("ACC-999")


def test_transcripts_for_acc002():
    hits = ds.search_transcripts("ACC-002")["hits"]
    assert [h["transcript_id"] for h in hits] == ["T-0001", "T-0002", "T-0003"]
    t3 = hits[-1]
    assert t3["source_id"] == "transcript:T-0003" and t3["date"] == "2026-09-27"
    assert "Operations team at the end of October" in t3["text"]
    assert "budget review" in t3["text"]
    assert [h["transcript_id"] for h in ds.search_transcripts("dana ruiz")["hits"]] == ["T-0001", "T-0002", "T-0003"]


def test_find_person():
    assert [m["source_id"] for m in ds.find_person("Dana Ruiz")["matches"]] == ["crm:contact/CON-010"]
    assert ds.find_person("marcus.oyelaran@pellwickfreight.example")["matches"] == []
    assert ds.find_person("Marcus Oyelaran")["matches"] == []


def test_unknown_account_returns_error():
    assert "error" in ds.get_account("ACC-999")


# ---- ACC-003 is never returned as related to ACC-001 ----


def test_lookalike_is_never_in_the_pellwick_freight_family():
    acc001 = ds.get_account("ACC-001")
    assert "ACC-003" not in json.dumps(acc001)
    acc003 = ds.get_account("ACC-003")
    assert acc003["parent"] is None and acc003["children"] == []
    assert "ACC-001" not in json.dumps(acc003) and "ACC-002" not in json.dumps(acc003)
    for name in [acc001["name"], *acc001["name_variants"], "Pellwick Freight (Marketing)", "PWF Marketing"]:
        for match in ds.search_accounts(name)["matches"]:
            family = [match["parent"], *match["children"]]
            if match["account_id"] in ("ACC-001", "ACC-002"):
                assert all(f is None or f["account_id"] != "ACC-003" for f in family)
            if match["account_id"] == "ACC-003":
                assert family == [None]


def test_lookalike_not_returned_for_full_company_name():
    assert "ACC-003" not in account_ids(ds.search_accounts("Pellwick Freight"))


# ---- Every record ID in the data is unique ----


def test_record_ids_are_unique():
    counts = Counter(ds.all_record_ids())
    assert [i for i, n in counts.items() if n > 1] == []


def test_answer_key_sources_exist_in_data():
    known = ds.all_source_ids()
    for case in json.loads(config.ANSWER_KEY_PATH.read_text()):
        for flag in case["required_flags"]:
            assert set(flag["any_source"]) <= known, flag
        for account_id in case["related_account_ids_required"] + case["related_account_ids_forbidden"]:
            assert f"crm:account/{account_id}" in known
