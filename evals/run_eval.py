"""Run every case in the answer key through the agent and print correctness results.

Calls the API. Usage: python -m evals.run_eval
"""

import json
import sys
import time

from evals.scorers import correctness
from lead_brief import config, data_store
from lead_brief.agent import brief_lead


def run_case(case: dict, known_source_ids: set[str], brief_fn=brief_lead) -> bool:
    """Brief one lead, print each check as PASS or FAIL, and return whether the case passed."""
    print(f"\n{case['case_id']} (lead {case['lead_id']})")
    start = time.monotonic()
    try:
        brief = brief_fn(case["lead_id"])
    except Exception as e:  # an agent failure is a failed case, not a crashed run
        print(f"  [FAIL] agent error after {time.monotonic() - start:.1f}s: {type(e).__name__}: {e}")
        print("  => FAIL")
        return False
    print(f"  {time.monotonic() - start:.1f}s | {brief.alert_level} | {brief.headline}")
    checks = correctness(brief, case, known_source_ids)
    for check in checks:
        print(f"  [{'PASS' if check.passed else 'FAIL'}] {check.name}: {check.detail}")
    passed = all(check.passed for check in checks)
    print(f"  => {'PASS' if passed else 'FAIL'}")
    return passed


def main() -> int:
    config.load_env()
    cases = json.loads(config.ANSWER_KEY_PATH.read_text(encoding="utf-8"))
    known = data_store.all_source_ids()
    print(
        f"Lead brief eval: model={config.AGENT_MODEL} prompt={config.PROMPT_VERSION} "
        f"tools={config.TOOL_VERSION} as_of={config.AS_OF_DATE} cases={len(cases)}"
    )
    results = [run_case(case, known) for case in cases]
    print(f"\nOverall: {sum(results)}/{len(results)} cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
