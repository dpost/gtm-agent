# Task 01: First end-to-end run (checkpoint: Tue Oct 6)

## Definition of done

1. `python -m lead_brief.agent L-001` prints a brief that validates against the `Brief` schema.
2. `python -m evals.run_eval` prints each correctness check for L-001 as pass or fail, plus an overall result.
3. `pytest` passes, with no API calls.
4. Git initialized, first commit made, remote repo private.

**A failing score still meets the checkpoint.** The goal today is that the loop runs and the score prints. Making the score good is later work.

## Not today

MLflow, LLM judges, the data generator, more cases, the MCP server, prompt tuning, README polish. If any of these come up, add a line to `NOTES.md` under "Later" and keep going.

## Build steps

1. **Scaffold:** `pyproject.toml`, `.gitignore` (include `.env`, `mlruns/`, `.venv/`), `src/lead_brief/config.py` with `AS_OF_DATE = "2026-10-06"`, model names, and prompt/tool version strings.
2. **Hand-write the L-001 data** (below) as JSON under `data/crm/` and `data/usage/`, and as `.txt` files under `data/transcripts/`. Write `data/answer_key/cases.json` first.
3. **`schema.py`:** the `Brief` model from SPEC.md. Enums:
   - `alert_level`: `routine`, `heads_up`, `caution`
   - `relationship_status`: `net_new`, `healthy_department`, `at_risk_department`, `closed_lost_history`, `job_changer`, `conflict`
   - flag `type`: `renewal_risk`, `champion_change`, `closed_lost_history`, `open_opp_conflict`, `stale_contact`, `warm_reference`, `job_changer`
4. **`data_store.py`:** load the data and implement the five tool functions from SPEC.md. `search_accounts` can be simple today (case-insensitive substring plus a name-variants list); it gets smarter later.
5. **`tools.py` and `agent.py`:** the tool schemas and a hand-written tool-use loop. Cap it at 10 tool calls. The final answer is JSON validated into `Brief`; retry once on a validation error, then fail loudly.
6. **`evals/scorers.py`:** correctness only, as code (checks listed below).
7. **`evals/run_eval.py`:** run every case in `cases.json` (just one today) and print the results.
8. **`tests/`:** tool functions return the right records for L-001; ACC-003 is never returned as related to ACC-001; every record ID in the data is unique.

## The L-001 case

This is a caution case that uses all three sources. It includes one look-alike company as a trap.

**Lead L-001:** Marcus Oyelaran, Director of FP&A, company field "Pellwick Freight", email `marcus.oyelaran@pellwickfreight.example`, inbound demo request on 2026-10-05.

**Accounts**
- **ACC-001: Pellwick Freight Holdings.** Parent account, not a customer itself. Name variants: "Pellwick Freight", "Pellwick".
- **ACC-002: Pellwick Freight (Marketing).** Child of ACC-001, an active customer. Name variant: "PWF Marketing". ARR $86,000; 120 licensed seats; renewal date 2026-11-20; account owner Riley Chen.
- **ACC-003: Pellwick Dental Group.** Unrelated look-alike, a healthy customer. Must not be linked to the lead.

**Opportunity OPP-004:** renewal for ACC-002, stage "Renewal: Negotiation", owner Riley Chen, close date 2026-11-20. Rep-entered MEDDPICC, last updated 2026-05-12:
- Champion: Dana Ruiz (CON-010), VP Marketing
- Economic buyer: Sam Whitfield (CON-011), CMO
- Pain: "Campaign reporting takes two days per week"

**Usage for ACC-002:** 12 weekly rows ending 2026-10-04. Active seats slide from about 96 (80%) to about 54 (45%), with the drop steepest in the last five weeks. Health score falls from green to red.

**Transcripts for ACC-002**
- **T-0001** (2026-06-10): QBR. Upbeat, Dana praises the dashboards.
- **T-0002** (2026-08-14): check-in. Mild, mentions a reorg is "being discussed."
- **T-0003** (2026-09-27): check-in. Dana says she moves to the Operations team at the end of October, no replacement is named for the tool, and Sam wants a budget review before renewal. This contradicts the CRM's champion field.

**ACC-003** gets one healthy usage history and one upbeat transcript (T-0004), so it looks like a plausible wrong answer.

## Answer key for L-001

```json
{
  "case_id": "L-001",
  "lead_id": "L-001",
  "relationship_status": "at_risk_department",
  "alert_level": "caution",
  "related_account_ids_required": ["ACC-001", "ACC-002"],
  "related_account_ids_forbidden": ["ACC-003"],
  "required_flags": [
    {"type": "renewal_risk", "any_source": ["usage:ACC-002", "crm:opp/OPP-004"]},
    {"type": "champion_change", "any_source": ["transcript:T-0003"]}
  ],
  "forbidden_flag_types": ["warm_reference"],
  "action_intent": "Coordinate with Riley Chen before calling; do not pitch."
}
```

## Correctness checks

Each check prints pass or fail. The case passes only if all checks pass.

1. `relationship_status` matches the key.
2. `alert_level` matches the key.
3. All required account IDs are present, and no forbidden ID is present.
4. Each required flag type is present and cites at least one of its `any_source` IDs.
5. No forbidden flag type is present.
6. Every cited `source_id` exists in the data. (Groundedness layer 1 is cheap, so it ships today.)

`action_intent` is for the actionability judge later. Do not score it today.

## First message to paste into Claude Code

> Read CLAUDE.md, SPEC.md, and tasks/01-first-end-to-end.md. Restate the definition of done, list the files you'll create, and flag anything ambiguous in one batch of questions. Then build it step by step, running each piece before moving on.
