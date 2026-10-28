"""Static HTML report for one eval run. Prototype: stdlib only, one self-contained file, no scripts from the web."""

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from evals.scorers import Check
from lead_brief.schema import Brief

LOUDNESS = {"routine": 0, "heads_up": 1, "caution": 2}


@dataclass
class CaseResult:
    case: dict
    seconds: float
    brief: Brief | None = None
    checks: list[Check] = field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and all(c.passed for c in self.checks)

    @property
    def failure_mode(self) -> str | None:
        """SPEC's named failure modes: 'false alarm' if the brief is louder than the key, 'buried signal' if quieter."""
        if self.brief is None:
            return None
        diff = LOUDNESS[self.brief.alert_level] - LOUDNESS[self.case["alert_level"]]
        return "false alarm" if diff > 0 else "buried signal" if diff < 0 else None


def _pct(n: int, total: int) -> str:
    return f"{100 * n / total:.0f}%" if total else "n/a"


def _bar_row(label: str, passed: int, total: int) -> str:
    width = 100 * passed / total if total else 0
    return (
        f'<tr><td class="label">{escape(label)}</td>'
        f'<td class="bar"><div class="track"><div class="fill" style="width:{width:.1f}%"></div></div></td>'
        f'<td class="num">{passed}/{total}</td><td class="num muted">{_pct(passed, total)}</td></tr>'
    )


def _tile(label: str, value: str, note: str = "", tone: str = "") -> str:
    return (
        f'<div class="tile {tone}"><div class="tile-label">{escape(label)}</div>'
        f'<div class="tile-value">{escape(value)}</div><div class="tile-note">{escape(note)}</div></div>'
    )


def _level(level: str) -> str:
    return f'<span class="level level-{escape(level)}">{escape(level)}</span>'


def _brief_html(brief: Brief) -> str:
    accounts = ", ".join(brief.related_account_ids) or "none"
    flags = "".join(
        f'<li><span class="flag-type">{escape(f.type)}</span> {escape(f.claim)} '
        + "".join(f"<code>{escape(s)}</code>" for s in f.source_ids)
        + "</li>"
        for f in brief.flags
    ) or '<li class="muted">No flags.</li>'
    return f"""
      <dl class="brief">
        <dt>Headline</dt><dd>{escape(brief.headline)}</dd>
        <dt>Relationship</dt><dd>{escape(brief.relationship_status)} (accounts: {escape(accounts)})</dd>
        <dt>Summary</dt><dd>{escape(brief.summary)}</dd>
        <dt>Flags</dt><dd><ul class="flags">{flags}</ul></dd>
        <dt>Call context</dt><dd>{escape(brief.call_context_note)}</dd>
        <dt>Recommended action</dt><dd>{escape(brief.recommended_action)}</dd>
      </dl>"""


def _case_html(r: CaseResult) -> str:
    case = r.case
    got_level = _level(r.brief.alert_level) if r.brief else '<span class="muted">no brief</span>'
    mode = f'<span class="mode">{escape(r.failure_mode)}</span>' if r.failure_mode else ""
    headline = escape(r.brief.headline) if r.brief else escape(r.error or "")
    checks = "".join(
        f'<li class="{"ok" if c.passed else "bad"}"><span class="mark">{"PASS" if c.passed else "FAIL"}</span>'
        f"<b>{escape(c.name)}</b> {escape(c.detail)}</li>"
        for c in r.checks
    )
    body = _brief_html(r.brief) if r.brief else f'<p class="error">Agent error: {escape(r.error or "")}</p>'
    return f"""
  <details class="case {"pass" if r.passed else "fail"}"{"" if r.passed else " open"}>
    <summary>
      <span class="verdict">{"PASS" if r.passed else "FAIL"}</span>
      <span class="case-id">{escape(case["case_id"])}</span>
      <span class="levels">{_level(case["alert_level"])} <span class="arrow">&rarr;</span> {got_level} {mode}</span>
      <span class="headline">{headline}</span>
      <span class="num muted">{r.seconds:.1f}s</span>
    </summary>
    <div class="case-body">
      <div class="col">
        <h4>Answer key</h4>
        <p>Lead <code>{escape(case["lead_id"])}</code>, expected <b>{escape(case["relationship_status"])}</b>.</p>
        <p class="muted">Intended action: {escape(case.get("action_intent", ""))}</p>
        <h4>Checks</h4>
        <ul class="checks">{checks or '<li class="muted">Not scored.</li>'}</ul>
      </div>
      <div class="col">
        <h4>Brief</h4>{body}
      </div>
    </div>
  </details>"""


def render(results: list[CaseResult], meta: dict[str, str]) -> str:
    """The whole report as one HTML string. `meta` is shown as run parameters, in order."""
    total = len(results)
    passed = sum(r.passed for r in results)
    false_alarms = sum(r.failure_mode == "false alarm" for r in results)
    buried = sum(r.failure_mode == "buried signal" for r in results)
    errors = sum(r.error is not None for r in results)
    seconds = [r.seconds for r in results]

    by_check: dict[str, list[bool]] = defaultdict(list)
    by_status: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        for c in r.checks:
            by_check[c.name].append(c.passed)
        by_status[r.case["relationship_status"]].append(r.passed)

    tiles = "".join([
        _tile("Cases passed", f"{passed}/{total}", _pct(passed, total) + " pass all checks",
              "good" if total and passed == total else ""),
        _tile("False alarms", str(false_alarms), "louder than the key", "bad" if false_alarms else ""),
        _tile("Buried signals", str(buried), "quieter than the key", "bad" if buried else ""),
        _tile("Agent errors", str(errors), "no valid brief", "bad" if errors else ""),
        _tile("Median latency", f"{statistics.median(seconds):.1f}s" if seconds else "n/a",
              f"{sum(seconds):.0f}s total"),
    ])
    params = "".join(f"<span><b>{escape(k)}</b> {escape(v)}</span>" for k, v in meta.items())
    check_note = f' <span class="muted">({errors} agent errors not scored)</span>' if errors else ""
    check_rows = "".join(_bar_row(name, sum(v), len(v)) for name, v in by_check.items())
    status_rows = "".join(_bar_row(name, sum(v), len(v)) for name, v in sorted(by_status.items()))
    cases = "".join(_case_html(r) for r in results)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lead Brief Eval</title>
<style>
:root {{
  --bg: #f7f7f5; --surface: #ffffff; --text: #1d1d1b; --muted: #6b6b66; --border: #e3e2dd;
  --good: #1f7a4d; --good-bg: #e6f3ec; --bad: #b3261e; --bad-bg: #fbe9e7;
  --accent: #3b5bdb; --track: #ecebe6;
  --routine: #6b6b66; --heads_up: #9a6700; --caution: #b3261e;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #161615; --surface: #1f1f1d; --text: #ecebe6; --muted: #9b9a94; --border: #33332f;
    --good: #5cc28f; --good-bg: #183026; --bad: #f2887f; --bad-bg: #3a1d1a;
    --accent: #8ea6ff; --track: #2c2c29;
    --routine: #9b9a94; --heads_up: #e3b341; --caution: #f2887f;
  }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text);
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 32px 16px 64px; }}
h1 {{ font-size: 22px; margin: 0 0 4px; }}
h2 {{ font-size: 15px; margin: 32px 0 12px; }}
h4 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); margin: 12px 0 6px; }}
code {{ font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--track);
  padding: 1px 5px; border-radius: 4px; margin-left: 4px; white-space: nowrap; }}
.muted {{ color: var(--muted); }}
.params {{ display: flex; flex-wrap: wrap; gap: 6px 16px; color: var(--muted); font-size: 13px; }}
.params b {{ color: var(--text); font-weight: 600; }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-top: 24px; }}
.tile {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }}
.tile-label {{ color: var(--muted); font-size: 12px; }}
.tile-value {{ font-size: 26px; font-weight: 650; font-variant-numeric: tabular-nums; }}
.tile-note {{ color: var(--muted); font-size: 12px; }}
.tile.good .tile-value {{ color: var(--good); }}
.tile.bad .tile-value {{ color: var(--bad); }}
.grid2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 0 24px; }}
table.bars {{ width: 100%; border-collapse: collapse; background: var(--surface);
  border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }}
table.bars td {{ padding: 7px 12px; border-top: 1px solid var(--border); }}
table.bars tr:first-child td {{ border-top: 0; }}
td.label {{ white-space: nowrap; }}
td.bar {{ width: 100%; }}
td.num, span.num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.track {{ height: 8px; background: var(--track); border-radius: 4px; overflow: hidden; }}
.fill {{ height: 100%; background: var(--accent); border-radius: 4px; }}
.toolbar {{ display: flex; align-items: center; justify-content: space-between; }}
.toolbar label {{ color: var(--muted); font-size: 13px; cursor: pointer; }}
body.failures-only details.pass {{ display: none; }}
details.case {{ background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--good);
  border-radius: 8px; margin-bottom: 8px; }}
details.case.fail {{ border-left-color: var(--bad); }}
summary {{ display: grid; grid-template-columns: 44px 64px auto 1fr auto; gap: 12px; align-items: center;
  padding: 10px 14px; cursor: pointer; list-style: none; }}
summary::-webkit-details-marker {{ display: none; }}
.verdict {{ font-size: 11px; font-weight: 700; color: var(--good); }}
.fail .verdict {{ color: var(--bad); }}
.case-id {{ font-weight: 600; }}
.headline {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.levels {{ white-space: nowrap; }}
.arrow {{ color: var(--muted); }}
.level {{ font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 10px; border: 1px solid currentColor; }}
.level-routine {{ color: var(--routine); }}
.level-heads_up {{ color: var(--heads_up); }}
.level-caution {{ color: var(--caution); }}
.mode {{ font-size: 11px; font-weight: 600; color: var(--bad); background: var(--bad-bg);
  padding: 2px 7px; border-radius: 10px; margin-left: 4px; }}
.case-body {{ display: grid; grid-template-columns: 1fr 1.4fr; gap: 24px; padding: 0 16px 16px;
  border-top: 1px solid var(--border); }}
.case-body p {{ margin: 4px 0; }}
ul.checks, ul.flags {{ list-style: none; padding: 0; margin: 0; }}
ul.checks li {{ padding: 3px 0; }}
.mark {{ display: inline-block; width: 40px; font-size: 11px; font-weight: 700; }}
.ok .mark {{ color: var(--good); }}
.bad .mark {{ color: var(--bad); }}
ul.flags li {{ margin-bottom: 6px; }}
.flag-type {{ font-weight: 600; margin-right: 4px; }}
dl.brief {{ margin: 0; display: grid; grid-template-columns: 130px 1fr; gap: 6px 12px; }}
dl.brief dt {{ color: var(--muted); }}
dl.brief dd {{ margin: 0; }}
.error {{ color: var(--bad); background: var(--bad-bg); padding: 8px 10px; border-radius: 6px; }}
@media (max-width: 720px) {{
  summary {{ grid-template-columns: 40px 1fr auto; }}
  summary .levels, summary .headline {{ grid-column: 1 / -1; }}
  summary > .num {{ grid-row: 1; grid-column: 3; }}
  .case-body {{ grid-template-columns: 1fr; }}
  dl.brief {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<main>
  <h1>Lead brief eval</h1>
  <div class="params">{params}</div>
  <div class="tiles">{tiles}</div>
  <div class="grid2">
    <section><h2>Pass rate by check{check_note}</h2><table class="bars">{check_rows}</table></section>
    <section><h2>Pass rate by situation</h2><table class="bars">{status_rows}</table></section>
  </div>
  <div class="toolbar">
    <h2>Cases</h2>
    <label><input type="checkbox" onchange="document.body.classList.toggle('failures-only', this.checked)"> Failures only</label>
  </div>
  {cases}
  <p class="muted">Prototype eval report. Synthetic data only. Failed cases open by default.</p>
</main>
</body>
</html>
"""


def write(results: list[CaseResult], meta: dict[str, str], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(results, meta), encoding="utf-8")
    return path
