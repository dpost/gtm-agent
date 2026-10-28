"""HTML report rendering from hand-built results. No API calls."""

import json

from evals import report
from evals.report import CaseResult
from evals.run_eval import run_case
from evals.scorers import correctness
from lead_brief import config, data_store
from lead_brief.schema import Brief
from tests.test_scorers import GOOD

CASE = json.loads(config.ANSWER_KEY_PATH.read_text())[0]
KNOWN = data_store.all_source_ids()
META = {"model": "test-model", "prompt": "agent-v1"}


def result(**changes) -> CaseResult:
    brief = Brief.model_validate({**GOOD, **changes})
    return CaseResult(CASE, 1.5, brief=brief, checks=correctness(brief, CASE, KNOWN))


def test_failure_modes_follow_loudness():
    assert result().failure_mode is None
    assert result(alert_level="heads_up").failure_mode == "buried signal"
    louder = {**CASE, "alert_level": "routine"}
    assert CaseResult(louder, 1.0, brief=Brief.model_validate(GOOD)).failure_mode == "false alarm"


def test_report_shows_cases_checks_and_escapes_text():
    html = report.render([result(), result(headline="<script>x</script>", alert_level="heads_up")], META)
    assert "1/2" in html and "test-model" in html
    assert "buried signal" in html and "alert_level" in html
    assert "<script>x" not in html and "&lt;script&gt;x" in html
    assert chr(0x2014) not in html  # no em dashes in generated text


def test_agent_error_is_a_failed_case_in_the_report(tmp_path):
    def broken(lead_id, trace):
        trace.append({"kind": "tool", "name": "search_accounts", "input": {"name": "Pellwick"}, "is_error": False})
        raise RuntimeError("boom")

    r = run_case(CASE, KNOWN, brief_fn=broken)
    assert not r.passed and r.error == "RuntimeError: boom"
    path = report.write([r], META, tmp_path / "out" / "report.html")
    html = path.read_text()
    assert "No valid brief. RuntimeError: boom" in html
    assert "search_accounts(name=&quot;Pellwick&quot;)" in html  # the trace up to the failure is kept


def test_report_shows_the_lead_input_the_retry_and_expected_vs_got():
    r = result()
    r.lead = data_store.get_lead("L-001")
    r.trace = [
        {"kind": "tool", "name": "search_accounts", "input": {"name": "Pellwick Freight"}, "is_error": False},
        {"kind": "retry", "error": "1 validation error for Brief", "output": '{"alert_level": "caution",'},
    ]
    html = report.render([r], META)
    assert "Marcus Oyelaran" in html and "Inbound demo request on 2026-10-05" in html
    assert "1 retry" in html and "1 validation error for Brief" in html
    assert "ACC-001, ACC-002; not ACC-003" in html  # related_accounts: answer key column
    assert r.retries == 1
