# Lead Brief Agent

A prototype pre-call brief agent for SDRs, plus the eval harness that measures it.

A rep gets a new inbound lead. Before dialing, they need one answer: do we already have a relationship with this company, and what do I need to know before I call? The agent checks a synthetic CRM, a usage scorecard, and call transcripts, then returns a short brief where every claim cites the record it came from.

## The claim

> Reps are doing a hundred things at once, so an agent has to stay quiet on routine leads and get loud on risky ones.

A brief that cries wolf on a routine lead, or buries the signal on a risky one, teaches reps to ignore it. So the brief carries an `alert_level` (`routine`, `heads_up`, or `caution`), and the eval checks that the loudness matches the situation, not only that the facts are right.

## Status

**Prototype, synthetic data, 40 eval cases scored for correctness. The LLM judges and MLflow tracking are next.**

What works today:

- A hand-written tool-use loop on the Anthropic Python SDK (no agent framework), capped at 10 tool calls.
- Five read-only data tools: `search_accounts`, `get_account`, `get_usage`, `search_transcripts`, `find_person`.
- A validated `Brief` schema (pydantic) with cited source IDs such as `crm:opp/OPP-004`, `usage:ACC-002`, `transcript:T-0003`.
- A correctness scorer with six code checks, run against 40 synthetic cases in SPEC's mix of six situations.
- A data generator and a checker: code makes every record and number, an LLM writes only transcript prose, and `scripts/check_data.py` verifies every planted fact landed.
- 46 fast tests that make no API calls.

The first case, L-001, was written by hand. It is a caution case: the lead's company has a sister department that is a customer at renewal risk, its champion is leaving, and there is a look-alike unrelated company in the CRM as a trap. On the first run the agent passed all six checks, stayed off the look-alike, and put "talk to the account owner before you call" in the headline.

The other 39 cases were generated from an answer key written first. Each situation has look-alike companies, name variants, or subsidiaries as traps, and two cases have a namesake: a contact with the lead's name who is someone else. The first 40-case run passed 36 of 40 cases on correctness alone (Oct 28). All four misses were on related accounts: the agent sometimes leaves the lead's own company account out of `related_account_ids`. 14 of the 40 briefs needed the one validation retry.

Not built yet: the groundedness and actionability LLM judges, judge calibration, MLflow tracking, and the MCP server. The plan is in [SPEC.md](SPEC.md).

## Run it

Needs Python 3.11+ and an Anthropic API key in `LEAD_BRIEF_ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEY` (checked in that order), either in the environment or in a gitignored `.env` at the repo root. Use the first name in Claude Code cloud sessions, which strip `ANTHROPIC_API_KEY`.

```bash
uv sync --extra dev
```

```bash
uv run python -m lead_brief.agent L-001
```

```bash
uv run python -m evals.run_eval
```

```bash
uv run pytest
```

```bash
uv run python scripts/check_data.py
```

To regenerate the data, run `uv run python scripts/generate_data.py`. It keeps transcripts already on disk unless their spec changed, so it calls the API only for new ones.

Each eval run also writes a self-contained HTML report to `reports/eval-<timestamp>.html` (gitignored): pass rate, false alarms and buried signals, retries, and for each case the lead (input), the agent's tool calls and any retry, the brief (output), and each check's answer key next to what the brief said.

Without `uv`: `python -m venv .venv`, activate it, `pip install -e ".[dev]"`, then drop the `uv run` prefix.

## Layout

```
data/answer_key/cases.json   expected answers, written before the data
data/answer_key/planted_facts.json  facts each case's data must contain
data/crm, usage, transcripts synthetic sources
src/lead_brief/              schema, data tools, tool schemas, agent loop, prompt
evals/                       correctness scorer, eval runner, HTML report
scripts/                     generate_data.py, check_data.py
tests/                       fast tests, no API calls
```

## Known limits

**Evidence**
- One run over 40 cases. Nothing yet says how much the pass rate moves between runs of the same agent.
- The same author wrote the answer key and the generator's world, so the cases test what the author thought to plant. Code generated the numbers and an LLM the transcript prose, which limits how much the data leans toward the agent.
- Only correctness is scored. Groundedness today means "every cited ID exists"; no judge yet checks that a claim matches its cited record. Actionability (does the loudness fit the situation) is not scored at all.
- The spec's "zero caution flags on routine cases" check is not implemented, because which flag types count as caution flags is not defined yet. That leaves the false-alarm failure mode unmeasured.
- Extra flags are not penalized unless their type is on the case's forbidden list. On L-001 the agent added a `stale_contact` flag the key did not ask for.
- Cost and latency per run are not logged.

**Agent and tools**
- `search_accounts` is a case-insensitive substring match plus a name-variants list. It does not match on email domain, fuzzy names, or a variant inside a longer query (for example "Pellwick Freight Inc").
- `search_transcripts` returns full transcript text. Fine at two or three short transcripts per account; it will not scale.
- Activity notes are empty on every account, because they need their own source ID convention first.
- The final brief is parsed from JSON with one retry on a validation error, not produced with structured outputs. On one live run the first answer added a field outside the schema and needed the retry, which costs time and tokens.
- Refusals fail loudly. There is no fallback model, so eval runs stay comparable.
- The "as of" date is fixed at 2026-10-06 to match the synthetic data.

**Scope**
- Read-only by design: no writing back to the CRM.
- No web search, Slack, UI, hosting, or auth. See "Out of scope for v1" in [SPEC.md](SPEC.md).

## Data

Every company, person, and record here is invented. The seller is Larkspur Analytics, a fictional analytics SaaS. Email addresses use the reserved `.example` domain. Nothing comes from any employer or client.

This is a prototype and a reference implementation, not production software.
