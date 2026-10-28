"""Static HTML report for one eval run. Prototype: stdlib only, one self-contained file.

Each case reads in the order the agent works: the lead (input), the agent run (tool calls, retries),
the brief (output), and the score against the answer key.
"""

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from evals.scorers import Check
from lead_brief.schema import Brief

LOUDNESS = {"routine": 0, "heads_up": 1, "caution": 2}

SITUATIONS = {
    "net_new": "Net new, no relationship",
    "healthy_department": "Healthy customer, other department",
    "at_risk_department": "At-risk customer, other department",
    "closed_lost_history": "Prior closed-lost deal",
    "job_changer": "Job changer from a customer",
    "conflict": "Another rep's opp or a stale contact",
}

CHECK_HELP = {
    "relationship_status": "Names the right situation, one of six.",
    "alert_level": "Loudness matches the situation.",
    "related_accounts": "Links the right accounts and none of the look-alikes.",
    "required_flags": "Raises each planted risk or opportunity, citing a record that holds it.",
    "forbidden_flags": "Raises none of the flags that would mislead the rep.",
    "source_ids_exist": "Every citation points at a real record.",
}

LEAD_FIELDS = [("title", "Title"), ("company", "Company (as typed)"), ("email", "Email"), ("form_note", "Form note")]


@dataclass
class CaseResult:
    case: dict
    seconds: float
    lead: dict = field(default_factory=dict)
    brief: Brief | None = None
    checks: list[Check] = field(default_factory=list)
    error: str | None = None
    trace: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.error is None and all(c.passed for c in self.checks)

    @property
    def retries(self) -> int:
        return sum(event["kind"] == "retry" for event in self.trace)

    @property
    def failure_mode(self) -> str | None:
        """SPEC's named failure modes: 'false alarm' if the brief is louder than the key, 'buried signal' if quieter."""
        if self.brief is None:
            return None
        diff = LOUDNESS[self.brief.alert_level] - LOUDNESS[self.case["alert_level"]]
        return "false alarm" if diff > 0 else "buried signal" if diff < 0 else None


def _pct(n: int, total: int) -> str:
    return f"{100 * n / total:.0f}%" if total else "n/a"


def _level(level: str, mismatch: bool = False) -> str:
    """Alert level as a loudness meter: one to three bars. Neutral on purpose: loudness is the
    expected answer, not a result, so it never borrows the pass or fail colors."""
    bars = "".join(f'<i class="{"on" if n <= LOUDNESS[level] else ""}"></i>' for n in range(3))
    return (
        f'<span class="level{" mismatch" if mismatch else ""}"><span class="meter" aria-hidden="true">{bars}</span>'
        f'{escape(level.replace("_", " "))}</span>'
    )


def _chip(text: str, tone: str) -> str:
    return f'<span class="chip chip-{tone}">{escape(text)}</span>'


def _tile(label: str, value: str, note: str, tone: str = "") -> str:
    return (
        f'<div class="tile {tone}"><div class="tile-label">{escape(label)}</div>'
        f'<div class="tile-value">{escape(value)}</div><div class="tile-note">{escape(note)}</div></div>'
    )


def _bar_row(label: str, help_text: str, passed: int, total: int) -> str:
    width = 100 * passed / total if total else 0
    return (
        f'<tr><td><div class="row-label">{escape(label)}</div><div class="row-help">{escape(help_text)}</div></td>'
        f'<td class="bar"><div class="track"><div class="fill" style="width:{width:.1f}%"></div></div></td>'
        f'<td class="num">{passed}/{total}</td></tr>'
    )


def _input_html(r: CaseResult) -> str:
    lead = r.lead
    if not lead:
        return f'<p class="muted">Lead <code>{escape(r.case["lead_id"])}</code> not loaded.</p>'
    rows = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(str(lead[key]))}</dd>" for key, label in LEAD_FIELDS if lead.get(key)
    )
    request = " on ".join(escape(str(lead[k])) for k in ("source", "created_date") if lead.get(k))
    return f"""
        <div class="lead-name">{escape(lead.get("name", ""))}</div>
        <div class="lead-request">{request}</div>
        <dl class="fields">{rows}</dl>
        <div class="cite"><code>{escape(lead.get("source_id", ""))}</code></div>"""


def _args(tool_input: dict) -> str:
    return ", ".join(f"{escape(k)}={escape(json.dumps(v))}" for k, v in tool_input.items())


def _pretty(text: str) -> str:
    """Tool results are JSON text; indent them for reading, and show anything else as is."""
    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except ValueError:
        return text


def _run_html(r: CaseResult) -> str:
    items, retries = [], []
    for event in r.trace:
        if event["kind"] == "tool":
            tag = _chip("error", "bad") if event["is_error"] else ""
            call = f'<code class="call">{escape(event["name"])}({_args(event["input"])})</code>{tag}'
            if "output" in event:
                items.append(
                    f'<li><details class="tool"><summary>{call}</summary>'
                    f'<pre>{escape(_pretty(event["output"]))}</pre></details></li>'
                )
            else:
                items.append(f"<li>{call}</li>")
        elif event["kind"] == "skipped":
            items.append(
                f'<li class="muted"><code class="call">{escape(event["name"])}({_args(event["input"])})</code>'
                f'{_chip("not run, call budget used", "muted")}</li>'
            )
        elif event["kind"] == "retry":
            retries.append(f"""
          <div class="retry">
            <div>{_chip("retry", "warn")} The final JSON failed validation, so the agent asked the model once for a corrected brief.</div>
            <details class="raw"><summary>Validation error and rejected output</summary>
              <pre>{escape(event["error"])}</pre><pre>{escape(event["output"])}</pre>
            </details>
          </div>""")
    tools = sum(e["kind"] == "tool" for e in r.trace)
    outcome = (
        f'<p class="error">No valid brief. {escape(r.error or "")}</p>' if r.error
        else f'<p class="muted">{tools} tool call{"" if tools == 1 else "s"}, {r.seconds:.1f}s, then the brief.</p>'
    )
    calls = (
        f'<p class="muted hint">Click a call to see what the tool returned.</p><ol class="calls">{"".join(items)}</ol>'
        if items else '<p class="muted">No tool calls recorded.</p>'
    )
    return calls + "".join(retries) + outcome


def _brief_html(brief: Brief) -> str:
    accounts = ", ".join(brief.related_account_ids) or "none"
    flags = "".join(
        f'<li><span class="flag-type">{escape(f.type.replace("_", " "))}</span> {escape(f.claim)} '
        + " ".join(f"<code>{escape(s)}</code>" for s in f.source_ids)
        + "</li>"
        for f in brief.flags
    ) or '<li class="muted">No flags.</li>'
    return f"""
        <div class="brief-card">
          <div class="brief-top">{_level(brief.alert_level)}
            <span class="muted">{escape(SITUATIONS.get(brief.relationship_status, brief.relationship_status))}, accounts {escape(accounts)}</span>
          </div>
          <p class="brief-headline">{escape(brief.headline)}</p>
          <p>{escape(brief.summary)}</p>
          <h4>Flags</h4><ul class="flags">{flags}</ul>
          <dl class="fields">
            <dt>Call context</dt><dd>{escape(brief.call_context_note)}</dd>
            <dt>Recommended action</dt><dd>{escape(brief.recommended_action)}</dd>
          </dl>
        </div>"""


def _score_html(r: CaseResult) -> str:
    rows = "".join(
        f'<tr class="{"ok" if c.passed else "bad"}">'
        f'<td><div class="row-label">{escape(c.name)}</div><div class="row-help">{escape(CHECK_HELP.get(c.name, ""))}</div></td>'
        f"<td>{escape(c.expected or c.detail)}</td><td>{escape(c.got)}</td>"
        f'<td class="result">{"Pass" if c.passed else "Fail"}</td></tr>'
        for c in r.checks
    )
    if r.brief and r.case.get("action_intent"):
        rows += (
            '<tr class="unscored"><td><div class="row-label">recommended_action</div>'
            '<div class="row-help">Judged by the actionability scorer, not built yet.</div></td>'
            f'<td>{escape(r.case["action_intent"])}</td><td>{escape(r.brief.recommended_action)}</td>'
            '<td class="result">Not scored</td></tr>'
        )
    if not rows:
        return '<p class="muted">Not scored: the agent produced no brief.</p>'
    return f"""
        <div class="table-wrap"><table class="score">
          <thead><tr><th>Check</th><th>Answer key</th><th>Brief</th><th>Result</th></tr></thead>
          <tbody>{rows}</tbody>
        </table></div>"""


def _case_html(r: CaseResult, open_by_default: bool) -> str:
    case = r.case
    expected = case["alert_level"]
    if r.brief is None:
        levels = f'<span class="k">key</span>{_level(expected)}{_chip("no brief", "bad")}'
    elif r.brief.alert_level == expected:
        levels = f'{_level(expected)}<span class="match">matches key</span>'
    else:
        levels = f'<span class="k">key</span>{_level(expected)}<span class="k">brief</span>{_level(r.brief.alert_level, True)}'
    chips = "".join([
        _chip(r.failure_mode, "bad") if r.failure_mode else "",
        _chip(f"{r.retries} retry" if r.retries == 1 else f"{r.retries} retries", "warn") if r.retries else "",
        _chip("agent error", "bad") if r.error else "",
    ])
    who = escape(r.lead.get("name", case["lead_id"]))
    company = escape(r.lead.get("company", ""))
    return f"""
  <details class="case {"pass" if r.passed else "fail"}"{" open" if open_by_default else ""}>
    <summary>
      <span class="verdict">{"Pass" if r.passed else "Fail"}</span>
      <span class="case-id">{escape(case["case_id"])}</span>
      <span class="who"><b>{who}</b> <span class="muted">{company}</span></span>
      <span class="levels">{levels}{chips}</span>
      <span class="num muted">{r.seconds:.1f}s</span>
    </summary>
    <div class="flow">
      <section class="step"><h3><span class="n">1</span>Input: the lead</h3>{_input_html(r)}</section>
      <section class="step"><h3><span class="n">2</span>Agent run</h3>{_run_html(r)}</section>
      <section class="step wide"><h3><span class="n">3</span>Output: the brief the rep sees</h3>
        {_brief_html(r.brief) if r.brief else '<p class="muted">No brief.</p>'}</section>
      <section class="step wide"><h3><span class="n">4</span>Score against the answer key</h3>
        <p class="muted">Expected situation: {escape(SITUATIONS.get(case["relationship_status"], case["relationship_status"]))}.</p>
        {_score_html(r)}</section>
    </div>
  </details>"""


def render(results: list[CaseResult], meta: dict[str, str]) -> str:
    """The whole report as one HTML string. `meta` is shown as run parameters, in order."""
    total = len(results)
    passed = sum(r.passed for r in results)
    false_alarms = sum(r.failure_mode == "false alarm" for r in results)
    buried = sum(r.failure_mode == "buried signal" for r in results)
    retried = sum(r.retries > 0 for r in results)
    errors = sum(r.error is not None for r in results)
    seconds = [r.seconds for r in results]

    by_check: dict[str, list[bool]] = defaultdict(list)
    by_status: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        for c in r.checks:
            by_check[c.name].append(c.passed)
        by_status[r.case["relationship_status"]].append(r.passed)

    tiles = "".join([
        _tile("Cases passed", f"{passed}/{total}", f"{_pct(passed, total)} pass every check",
              "good" if total and passed == total else "bad" if passed < total else ""),
        _tile("False alarms", str(false_alarms), "louder than the key", "bad" if false_alarms else ""),
        _tile("Buried signals", str(buried), "quieter than the key", "bad" if buried else ""),
        _tile("Needed a retry", str(retried), "invalid JSON on first try", "warn" if retried else ""),
        _tile("Agent errors", str(errors), "no valid brief", "bad" if errors else ""),
        _tile("Median time", f"{statistics.median(seconds):.1f}s" if seconds else "n/a", f"{sum(seconds):.0f}s total"),
    ])
    legend = (
        '<span class="legend-lead">Alert level is how loud the brief should be. The answer key sets it, and the brief has to match.</span>'
        f'<span>{_level("routine")} quiet: skim and dial</span>'
        f'<span>{_level("heads_up")} an opening to use</span>'
        f'<span>{_level("caution")} a risk: change the approach</span>'
    )
    params = "".join(f"<span>{escape(k)} <b>{escape(v)}</b></span>" for k, v in meta.items())
    check_note = f" ({errors} agent errors not scored)" if errors else ""
    check_rows = "".join(_bar_row(n, CHECK_HELP.get(n, ""), sum(v), len(v)) for n, v in by_check.items())
    status_rows = "".join(
        _bar_row(SITUATIONS.get(s, s), s, sum(v), len(v)) for s, v in sorted(by_status.items())
    )
    cases = "".join(_case_html(r, total <= 5 or not r.passed) for r in results)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Lead Brief Eval</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>
/* Layout: an eval sheet. Summary first, then each case read in the agent's order: lead, run, brief, score. */
:root {{
  --paper: #f4f5f7; --surface: #ffffff; --ink: #171b23; --muted: #5d6573; --rule: #dde1e8; --wash: #eceef3;
  --accent: #3446a6;
  --pass: #1d7348; --pass-wash: #e3f2ea; --fail: #b02a1f; --fail-wash: #fbe8e5; --warn: #8a5a00; --warn-wash: #fbf0d9;
  --sans: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper: #121419; --surface: #1a1d24; --ink: #e8eaf0; --muted: #9aa1ae; --rule: #2d323c; --wash: #23272f;
    --accent: #9cadff;
    --pass: #63c690; --pass-wash: #17301f; --fail: #f08a80; --fail-wash: #3a1c19; --warn: #e2b450; --warn-wash: #33290f;
    color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --paper: #121419; --surface: #1a1d24; --ink: #e8eaf0; --muted: #9aa1ae; --rule: #2d323c; --wash: #23272f;
  --accent: #9cadff;
  --pass: #63c690; --pass-wash: #17301f; --fail: #f08a80; --fail-wash: #3a1c19; --warn: #e2b450; --warn-wash: #33290f;
  color-scheme: dark;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 15px/1.55 var(--sans); }}
main {{ max-width: 1120px; margin: 0 auto; padding-block: 40px 72px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: flex; flex-direction: column; gap: 28px; }}
h1 {{ font-size: 28px; font-weight: 700; letter-spacing: -0.01em; margin: 0; text-wrap: balance; }}
h2 {{ font-size: 17px; font-weight: 600; margin: 0; }}
h3 {{ display: flex; align-items: center; gap: 8px; margin: 0 0 10px; font-size: 12px; font-weight: 600;
  letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }}
h4 {{ margin: 12px 0 4px; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }}
p {{ margin: 0; }}
code, pre {{ font-family: var(--mono); font-size: 12.5px; }}
code {{ background: var(--wash); padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere; }}
.muted {{ color: var(--muted); }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}

.intro {{ display: flex; flex-direction: column; gap: 10px; }}
.lede {{ max-width: 68ch; font-size: 16px; }}
.legend {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px 18px; font-size: 13.5px; color: var(--muted); }}
.legend-lead {{ flex-basis: 100%; }}
.legend .level {{ margin-right: 6px; }}
.params {{ display: flex; flex-wrap: wrap; gap: 4px 18px; font: 12.5px var(--mono); color: var(--muted); }}
.params b {{ color: var(--ink); font-weight: 500; }}

.tiles {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }}
.tile {{ background: var(--surface); border: 1px solid var(--rule); border-radius: 8px; padding: 12px 14px; min-width: 0; }}
.tile-label {{ font-size: 12.5px; color: var(--muted); }}
.tile-value {{ font-size: 26px; font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1.3; }}
.tile-note {{ font-size: 12px; color: var(--muted); }}
.tile.good .tile-value {{ color: var(--pass); }}
.tile.bad .tile-value {{ color: var(--fail); }}
.tile.warn .tile-value {{ color: var(--warn); }}

.cases-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }}
.cases-head label {{ font-size: 13.5px; color: var(--muted); cursor: pointer; display: flex; gap: 6px; align-items: center; }}
.case-list {{ display: flex; flex-direction: column; gap: 12px; }}
body.failures-only details.pass {{ display: none; }}

details.case {{ background: var(--surface); border: 1px solid var(--rule); border-radius: 10px; }}
details.case > summary {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; padding: 12px 16px;
  cursor: pointer; list-style: none; }}
details.case > summary::-webkit-details-marker {{ display: none; }}
details.case[open] > summary {{ border-bottom: 1px solid var(--rule); }}
.verdict {{ font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
  padding: 2px 8px; border-radius: 4px; color: var(--pass); background: var(--pass-wash); }}
.fail .verdict {{ color: var(--fail); background: var(--fail-wash); }}
.case-id {{ font: 500 13px var(--mono); }}
.who {{ flex: 1 1 200px; min-width: 0; }}
.levels {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }}
.k {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }}
.num {{ font-variant-numeric: tabular-nums; }}

.level {{ display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; white-space: nowrap;
  padding: 1px 8px 1px 6px; border-radius: 4px; background: var(--wash); color: var(--ink); }}
.level.mismatch {{ background: var(--fail-wash); color: var(--fail); }}
.meter {{ display: inline-flex; align-items: flex-end; gap: 2px; height: 12px; }}
.meter i {{ display: block; width: 4px; border-radius: 1px; background: var(--rule); }}
.meter i:nth-child(1) {{ height: 5px; }}
.meter i:nth-child(2) {{ height: 8px; }}
.meter i:nth-child(3) {{ height: 12px; }}
.meter i.on {{ background: currentColor; }}
.match {{ font-size: 12.5px; color: var(--pass); }}
.chip {{ font-size: 12px; font-weight: 600; padding: 1px 8px; border-radius: 10px; white-space: nowrap; margin-left: 6px; }}
.chip-bad {{ color: var(--fail); background: var(--fail-wash); }}
.chip-warn {{ color: var(--warn); background: var(--warn-wash); }}
.chip-muted {{ color: var(--muted); background: var(--wash); }}
.levels .chip {{ margin-left: 0; }}

.flow {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr); }}
.step {{ padding: 16px; min-width: 0; border-top: 1px solid var(--rule); }}
.step:nth-child(-n+2) {{ border-top: 0; }}
.step:nth-child(2) {{ border-left: 1px solid var(--rule); }}
.step.wide {{ grid-column: 1 / -1; }}
.n {{ display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 50%;
  background: var(--ink); color: var(--surface); font-size: 11px; letter-spacing: 0; }}

.lead-name {{ font-size: 17px; font-weight: 600; }}
.lead-request {{ color: var(--muted); margin-bottom: 8px; }}
dl.fields {{ display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 4px 14px; margin: 8px 0 0; }}
dl.fields dt {{ color: var(--muted); }}
dl.fields dd {{ margin: 0; min-width: 0; overflow-wrap: anywhere; }}
.cite {{ margin-top: 10px; }}

.hint {{ font-size: 13px; margin-bottom: 6px; }}
ol.calls {{ margin: 0 0 10px; padding-left: 22px; display: flex; flex-direction: column; gap: 5px; }}
ol.calls li::marker {{ color: var(--muted); font: 12px var(--mono); }}
code.call {{ background: none; padding: 0; }}
details.tool > summary {{ cursor: pointer; list-style: none; display: flex; align-items: baseline; gap: 6px;
  border-radius: 4px; padding: 1px 4px; margin-left: -4px; }}
details.tool > summary::-webkit-details-marker {{ display: none; }}
details.tool > summary::before {{ content: "▸"; color: var(--accent); font-size: 11px; flex: none; transition: transform .15s; }}
details.tool[open] > summary::before {{ transform: rotate(90deg); }}
details.tool > summary:hover {{ background: var(--wash); }}
details.tool > summary:hover code.call {{ color: var(--accent); }}
details.tool pre {{ margin: 6px 0 4px; padding: 10px 12px; background: var(--wash); border-radius: 6px;
  white-space: pre-wrap; overflow-wrap: anywhere; max-height: 360px; overflow: auto; font-size: 12px; }}
@media (prefers-reduced-motion: reduce) {{ details.tool > summary::before {{ transition: none; }} }}
.retry {{ display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }}
.retry .chip {{ margin: 0 6px 0 0; }}
details.raw summary {{ cursor: pointer; color: var(--accent); font-size: 13.5px; }}
details.raw pre {{ margin: 6px 0 0; padding: 10px; background: var(--wash); border-radius: 6px; white-space: pre-wrap;
  overflow-wrap: anywhere; max-height: 220px; overflow: auto; }}
.error {{ color: var(--fail); background: var(--fail-wash); padding: 8px 10px; border-radius: 6px; overflow-wrap: anywhere; }}

.brief-card {{ max-width: 760px; border: 1px solid var(--rule); border-radius: 8px;
  padding: 14px 18px; display: flex; flex-direction: column; gap: 8px; background: var(--surface); }}
.brief-top {{ display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; font-size: 13.5px; }}
.brief-headline {{ font-size: 17px; font-weight: 600; line-height: 1.4; text-wrap: balance; }}
ul.flags {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }}
.flag-type {{ font-weight: 600; margin-right: 4px; }}

.table-wrap {{ overflow-x: auto; margin-top: 8px; }}
table {{ border-collapse: collapse; width: 100%; }}
table.score {{ min-width: 640px; }}
table.score th {{ text-align: left; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--muted); padding: 6px 10px; border-bottom: 1px solid var(--rule); }}
table.score td {{ padding: 8px 10px; border-bottom: 1px solid var(--rule); vertical-align: top; }}
table.score td:nth-child(2), table.score td:nth-child(3) {{ width: 32%; }}
td.result {{ font-weight: 600; white-space: nowrap; }}
tr.ok td.result {{ color: var(--pass); }}
tr.bad td.result {{ color: var(--fail); }}
tr.bad {{ background: var(--fail-wash); }}
tr.unscored td {{ color: var(--muted); }}
.row-label {{ font: 500 13px var(--mono); }}
.row-help {{ font-size: 12.5px; color: var(--muted); }}

.breakdown {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; }}
.breakdown section {{ display: flex; flex-direction: column; gap: 10px; min-width: 0; }}
table.bars {{ background: var(--surface); border: 1px solid var(--rule); border-radius: 8px; }}
table.bars td {{ padding: 8px 12px; border-top: 1px solid var(--rule); }}
table.bars tr:first-child td {{ border-top: 0; }}
td.bar {{ width: 40%; }}
td.num {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
.track {{ height: 8px; background: var(--wash); border-radius: 4px; overflow: hidden; }}
.fill {{ height: 100%; background: var(--accent); }}
footer {{ font-size: 13px; color: var(--muted); }}

@media (max-width: 900px) {{
  .tiles {{ grid-template-columns: repeat(3, 1fr); }}
  .breakdown {{ grid-template-columns: minmax(0, 1fr); }}
}}
@media (max-width: 640px) {{
  .tiles {{ grid-template-columns: repeat(2, 1fr); }}
  .flow {{ grid-template-columns: minmax(0, 1fr); }}
  .step:nth-child(2) {{ border-left: 0; border-top: 1px solid var(--rule); }}
}}
</style>
</head>
<body>
<main>
  <header class="intro">
    <h1>Lead brief eval</h1>
    <p class="lede">Each case gives the agent one inbound sales lead. The agent looks the company up in a synthetic CRM,
      a product usage scorecard, and call transcripts, then writes a pre-call brief for the rep. Code scores the brief
      against an answer key written before the data. A case passes only if every check passes.</p>
    <div class="legend">{legend}</div>
    <div class="params">{params}</div>
  </header>
  <div class="tiles">{tiles}</div>
  <section class="case-list">
    <div class="cases-head">
      <h2>Cases</h2>
      <label for="failures-only"><input type="checkbox" id="failures-only"
        onchange="document.body.classList.toggle('failures-only', this.checked)"> Failures only</label>
    </div>
    {cases}
  </section>
  <div class="breakdown">
    <section><h2>Pass rate by check{check_note}</h2><table class="bars">{check_rows}</table></section>
    <section><h2>Pass rate by situation</h2><table class="bars">{status_rows}</table></section>
  </div>
  <footer>Prototype eval report. Every company, person, and record is synthetic.</footer>
</main>
</body>
</html>
"""


def write(results: list[CaseResult], meta: dict[str, str], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(results, meta), encoding="utf-8")
    return path
