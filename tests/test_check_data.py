"""The generated data passes check_data, and check_data catches broken plants. No API calls."""

import copy
import json
from collections import Counter

import pytest

from lead_brief import config, data_store as ds
from scripts.check_data import Checker


@pytest.fixture
def checker():
    """A Checker over a private copy of the data, safe to mutate."""
    c = Checker()
    c.data = copy.deepcopy(c.data)
    c.transcripts = {t["transcript_id"]: t for t in c.data["transcripts"]}
    return c


def test_check_data_passes():
    assert Checker().run() == []


def test_answer_key_has_specs_case_mix():
    cases = json.loads(config.ANSWER_KEY_PATH.read_text())
    assert Counter(c["relationship_status"] for c in cases) == {
        "net_new": 8, "healthy_department": 8, "at_risk_department": 6,
        "closed_lost_history": 6, "job_changer": 6, "conflict": 6,
    }
    assert [c["lead_id"] for c in cases] == [f"L-{n:03d}" for n in range(1, 41)]


def test_every_kind_of_record_id_is_unique():
    for ids in (
        ds.all_record_ids(),
        [t["transcript_id"] for t in ds._load()["raw"]["transcripts"]],
        [u["account_id"] for u in ds._load()["raw"]["usage"]],
    ):
        assert [i for i, n in Counter(ids).items() if n > 1] == []


def test_catches_a_missing_planted_line(checker):
    t = checker.transcripts["T-0045"]
    t["text"] = t["text"].replace("SAML single sign-on", "single sign-on")
    assert any("T-0045" in p for p in checker.run())


def test_catches_a_usage_trend_that_did_not_land(checker):
    weeks = checker.data["usage"]["ACC-031"]["weeks"]
    for w in weeks:
        w.update(utilization_pct=85.0, health_band="green")
    assert any("usage:ACC-031 should be declining" in p for p in checker.run())


def test_catches_a_lookalike_wired_into_the_family(checker):
    checker.data["accounts"]["ACC-032"]["parent_account_id"] = "ACC-030"
    problems = checker.run()
    assert any(p.startswith("L-018") and "ACC-032" in p for p in problems)


def test_catches_a_net_new_lead_that_matches_an_account(checker):
    checker.data["accounts"]["ACC-004"]["name_variants"].append("Brannock Logistics")
    assert any(p.startswith("L-003") for p in checker.run())


def test_catches_an_open_opp_that_is_not_open(checker):
    checker.data["opps"]["OPP-022"]["status"] = "closed_lost"
    assert any(p.startswith("L-035") and "OPP-022" in p for p in checker.run())


def test_catches_an_em_dash_in_the_data(checker, tmp_path, monkeypatch):
    (tmp_path / "x.txt").write_text("a \u2014 b")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    checker.check_records()
    assert any("em or en dash" in p for p in checker.problems)
