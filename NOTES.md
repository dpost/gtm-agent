# Notes

Working notes for the lead brief prototype.

## Next

- **More eval cases: the 40 generated leads (SPEC milestone, Oct 9, overdue).** Only L-001 exists, so pass rates, the by-situation breakdown, and the false alarm and buried signal counts don't mean much yet. Follow SPEC's case mix and order: write all 40 answers in `data/answer_key/cases.json` first, then `scripts/generate_data.py` (code makes every number, an LLM writes only transcript prose), then `scripts/check_data.py` to verify each planted fact landed. Spread name variants, subsidiaries, and look-alike companies across all six situations.
- **Decide how job changes appear in the CRM before generating the job_changer cases.** Contacts carry an `employment_history` list today (SPEC's "Synthetic world" table calls for it), but standard CRM contact objects don't track a person's past employers: a contact belongs to one account. In real CRMs a job change usually shows up as an old contact record left at the former account (often marked inactive, with a bounced email or a stale `last_updated`), the person arriving as a new lead with a new email, and sometimes an account-contact relationship with start and end dates, or a job-change alert from a third-party enrichment tool. A realistic option: drop `employment_history`, keep separate contact records per employer, and make the agent connect them by name through `find_person`, with a namesake trap in some cases. This is a SPEC change, so log it in SPEC's Change Log with the reason.
- **Structured outputs for the final brief.** `output_config.format` with the Brief JSON schema, instead of parse plus one retry. Decided Oct 28: this is the Oct 13 "one change", made after the 40-case baseline run lands so the next 40-case run measures it (retries, time, pass rate). Seen on the first live eval run (Oct 6): the model's first answer added a field outside the schema (`flags_note`), validation rejected it, and the one retry fixed it. Structured outputs would rule this out and save the retry's cost and latency. Seen again on Oct 28: the first answer was invalid JSON (a trailing `,"` before the closing brace), and the retry fixed it. It happened again on a later Oct 28 run (report `eval-20261028-062611`), this time the same extra `flags_note` field as Oct 6, set to null. So roughly every other live run needs the retry so far, and two of the three failures are that same invented field. Eval reports now count retries per run, so the baseline shows the rate before the change.

## Later

- **Server-side refusal fallback** (`fallbacks: "default"`) is left out. On the current agent model it only reroutes `cyber` and `frontier_llm` declines, neither plausible for sales briefs, and a silent switch to another model would muddy eval comparisons. Refusals fail loudly instead.
- **Smarter `search_accounts`.** Match on email domain, fuzzy names, and the reverse substring direction (a variant inside the query, e.g. "Pellwick Freight Inc").
- **`search_transcripts` returns full text.** Fine at 2 to 3 short transcripts per account. Revisit (snippets plus a `get_transcript` tool) if transcripts grow.
- **Activity notes.** `activity` is an empty list on every account today. Notes need their own IDs, which needs a source ID convention (e.g. `crm:activity/ACT-001`) added to CLAUDE.md first.
- **Routine-case check.** SPEC's "zero caution flags on routine cases" is not in today's six checks. It needs a definition of which flag types count as caution flags.
- **HTML report into MLflow.** Log each run's `reports/eval-*.html` as an MLflow artifact next to the per-case table (Oct 9). Add token cost to the report once it is logged.
- **Cost and latency per run.** Log token usage and wall time per case (MLflow, Oct 9).

## Decisions (Oct 6)

- The lead record goes into the first user message, cited as `crm:lead/L-001`. None of the five SPEC tools fetches a lead.
- `call_context_note` holds one or two sentences on the lead themself and their inbound request (who, what they asked for, when).
- `.env` is read by a 10-line loader in `config.py` rather than adding `python-dotenv`.
- The API key is read from `LEAD_BRIEF_ANTHROPIC_API_KEY` first, then `ANTHROPIC_API_KEY`. Cloud environments strip `ANTHROPIC_API_KEY`, and their API credentials feature never attaches keys to `api.anthropic.com`, so the project-specific variable is the only way to run live in a cloud session. Use a dedicated key with a low spend limit there, since environment variables are readable inside sessions.
- At the 10-call cap, extra calls in the same turn get an error result, and the next request sends `tool_choice: none` with the same `tools` list, so the history stays append-only.
