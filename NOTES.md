# Notes

Working notes for the lead brief prototype.

## Next

- **The rest of the Oct 9 milestone: groundedness and actionability judges, and the baseline in MLflow.** The 40 cases now exist (Oct 28): `data/answer_key/cases.json`, `data/answer_key/planted_facts.json`, `scripts/generate_data.py`, and `scripts/check_data.py`. The first 40-case run scores correctness only.
- **Structured outputs for the final brief.** `output_config.format` with the Brief JSON schema, instead of parse plus one retry. Decided Oct 28: this is the Oct 13 "one change", made after the 40-case baseline run lands so the next 40-case run measures it (retries, time, pass rate). Seen on the first live eval run (Oct 6): the model's first answer added a field outside the schema (`flags_note`), validation rejected it, and the one retry fixed it. Structured outputs would rule this out and save the retry's cost and latency. Seen again on Oct 28: the first answer was invalid JSON (a trailing `,"` before the closing brace), and the retry fixed it. It happened again on a later Oct 28 run (report `eval-20261028-062611`), this time the same extra `flags_note` field as Oct 6, set to null. So roughly every other live run needs the retry so far, and two of the three failures are that same invented field. Eval reports now count retries per run, so the baseline shows the rate before the change.

## Later

- **Server-side refusal fallback** (`fallbacks: "default"`) is left out. On the current agent model it only reroutes `cyber` and `frontier_llm` declines, neither plausible for sales briefs, and a silent switch to another model would muddy eval comparisons. Refusals fail loudly instead.
- **Smarter `search_accounts`.** Match on email domain, fuzzy names, and the reverse substring direction (a variant inside the query, e.g. "Pellwick Freight Inc").
- **`search_transcripts` returns full text.** Fine at 2 to 3 short transcripts per account. Revisit (snippets plus a `get_transcript` tool) if transcripts grow.
- **Activity notes.** `activity` is an empty list on every account today. Notes need their own IDs, which needs a source ID convention (e.g. `crm:activity/ACT-001`) added to CLAUDE.md first.
- **Routine-case check.** SPEC's "zero caution flags on routine cases" is not in today's six checks. It needs a definition of which flag types count as caution flags.
- **HTML report into MLflow.** Log each run's `reports/eval-*.html` as an MLflow artifact next to the per-case table (Oct 9). Add token cost to the report once it is logged.
- **Cost and latency per run.** Log token usage and wall time per case (MLflow, Oct 9).
- **`related_account_ids` and the lead's own account.** First 40-case run (Oct 28, `reports/eval-20261028-065156.html`): 36/40 passed correctness, and all four misses were `related_accounts`. On L-025, L-037, and L-038 the lead's company is a single account and the agent returned an empty list; on L-022 it listed the sister accounts but not Clarion Billing, the lead's own company. Seven other single-account cases got it right. The answer key follows L-001, where the lead's own account (ACC-001) is required. The prompt says "every account in the same corporate family as the lead's company (parent, children, and siblings)", which doesn't say whether the lead's own account counts. Not tuned yet: a prompt change needs a version bump and its own measured run.
- **Validation retries on the 40-case baseline.** The same run needed the one validation retry on 14 of 40 briefs, none failed twice. That is the baseline rate for the structured outputs change above.
- **The cases may be too easy for correctness.** 90% on the first run, and every at-risk, job changer, and namesake case passed. Harder variants for a later round: a lead whose company field is misspelled, a subsidiary on a different domain with no name overlap, a namesake at a customer with no recency signal, an at-risk account whose decline is only in usage (no transcript says so).
- **Run eval cases in parallel.** `run_eval` briefs the 40 leads one after another. A small thread pool would cut wall time; keep the report order by case ID.
- **Drop `employment_history` from contacts.** Standard CRM contacts belong to one account and don't track past employers. The job changer cases no longer rely on it (see Decisions, Oct 28), so it can go, with a SPEC Change Log entry.
- **Data version in eval runs.** The data changed on Oct 28 (40 cases), but run metadata names only the model, prompt, and tool versions. Add a data version string to `config.py` and the report header so runs before and after a data change aren't compared by mistake.

## Decisions (Oct 6)

- The lead record goes into the first user message, cited as `crm:lead/L-001`. None of the five SPEC tools fetches a lead.
- `call_context_note` holds one or two sentences on the lead themself and their inbound request (who, what they asked for, when).
- `.env` is read by a 10-line loader in `config.py` rather than adding `python-dotenv`.
- The API key is read from `LEAD_BRIEF_ANTHROPIC_API_KEY` first, then `ANTHROPIC_API_KEY`. Cloud environments strip `ANTHROPIC_API_KEY`, and their API credentials feature never attaches keys to `api.anthropic.com`, so the project-specific variable is the only way to run live in a cloud session. Use a dedicated key with a low spend limit there, since environment variables are readable inside sessions.
- At the 10-call cap, extra calls in the same turn get an error result, and the next request sends `tool_choice: none` with the same `tools` list, so the history stays append-only.


## Decisions (Oct 28)

- **Planted facts sit beside the answer key.** `cases.json` keeps its shape. `data/answer_key/planted_facts.json`, written with it and before the data, lists what each case's data must contain in checkable form: usage trends, the exact sentence a named speaker says in a transcript, opportunity fields, contact dates, MEDDPICC dates, lead form notes. The generator reads the transcript sentences from it, and `check_data.py` verifies all of it.
- **Generated data is reproducible.** Usage numbers come from a random generator seeded with the account ID. Transcripts already on disk are kept when their header matches and they still contain their planted lines, so rerunning `generate_data.py` calls the API only for missing or changed transcripts (`--offline` refuses to call it, `--force-transcripts` rewrites them all). Transcript prose comes from `TRANSCRIPT_MODEL` in `config.py` at low effort.
- **Job changers are separate contact records.** The lead's earlier contact record stays at the former customer with the old email domain, and its `employment_history` lists only that employer (two of six carry an end date a rep entered). The link is made by name through `find_person`, backed by a transcript line, a form note, or the end date, never by an `employment_history` entry naming the new company. So the six cases still hold if `employment_history` is later dropped. Two namesake traps (L-006, L-034) have a same-named contact who is clearly someone else.
- **Routine cases forbid every flag type.** The eight net new cases list all seven flag types in `forbidden_flag_types`, which covers SPEC's "zero caution flags on routine cases" for now (see "Routine-case check" under Later).
- **L-001's hand-written records are never regenerated.** `generate_data.py` keeps them by ID and only adds new records around them.
