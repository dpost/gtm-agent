"""Run every case in the answer key through the agent, print correctness results, and write an HTML report.

Calls the API. Usage: python -m evals.run_eval
"""

import json
import sys
import time
from datetime import datetime

from evals import report
from evals.report import CaseResult
from evals.scorers import correctness
from lead_brief import config, data_store
from lead_brief.agent import brief_lead


def run_case(case: dict, known_source_ids: set[str], brief_fn=brief_lead) -> CaseResult:
    """Brief one lead, print each check as PASS or FAIL, and return the result."""
    print(f"\n{case['case_id']} (lead {case['lead_id']})")
    lead = data_store.get_lead(case["lead_id"])
    trace: list[dict] = []
    start = time.monotonic()
    try:
        brief = brief_fn(case["lead_id"], trace=trace)
    except Exception as e:  # an agent failure is a failed case, not a crashed run
        seconds = time.monotonic() - start
        print(f"  [FAIL] agent error after {seconds:.1f}s: {type(e).__name__}: {e}")
        print("  => FAIL")
        return CaseResult(case, seconds, lead=lead, error=f"{type(e).__name__}: {e}", trace=trace)
    seconds = time.monotonic() - start
    tools = sum(event["kind"] == "tool" for event in trace)
    print(f"  {seconds:.1f}s | {tools} tool calls | {brief.alert_level} | {brief.headline}")
    checks = correctness(brief, case, known_source_ids)
    for check in checks:
        print(f"  [{'PASS' if check.passed else 'FAIL'}] {check.name}: {check.detail}")
    result = CaseResult(case, seconds, lead=lead, brief=brief, checks=checks, trace=trace)
    print(f"  => {'PASS' if result.passed else 'FAIL'}")
    return result


def main() -> int:
    config.load_env()
    cases = json.loads(config.ANSWER_KEY_PATH.read_text(encoding="utf-8"))
    known = data_store.all_source_ids()
    started = datetime.now()
    print(
        f"Lead brief eval: model={config.AGENT_MODEL} prompt={config.PROMPT_VERSION} "
        f"tools={config.TOOL_VERSION} as_of={config.AS_OF_DATE} cases={len(cases)}"
    )
    results = [run_case(case, known) for case in cases]
    print(f"\nOverall: {sum(r.passed for r in results)}/{len(results)} cases passed")
    meta = {
        "run": started.strftime("%Y-%m-%d %H:%M"),
        "model": config.AGENT_MODEL,
        "prompt": config.PROMPT_VERSION,
        "tools": config.TOOL_VERSION,
        "as of": config.AS_OF_DATE,
    }
    path = report.write(results, meta, config.REPORTS_DIR / f"eval-{started:%Y%m%d-%H%M%S}.html")
    print(f"Report: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
