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
    def broken(lead_id):
        raise RuntimeError("boom")

    r = run_case(CASE, KNOWN, brief_fn=broken)
    assert not r.passed and r.error == "RuntimeError: boom"
    path = report.write([r], META, tmp_path / "out" / "report.html")
    assert "Agent error: RuntimeError: boom" in path.read_text()
