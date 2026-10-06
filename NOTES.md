# Notes

Working notes for the lead brief prototype.

## Later

- **Structured outputs for the final brief.** `output_config.format` with the Brief JSON schema, instead of parse plus one retry. A candidate for the Oct 13 "one change". Seen on the first live eval run (Oct 6): the model's first answer added a field outside the schema (`flags_note`), validation rejected it, and the one retry fixed it. Structured outputs would rule this out and save the retry's cost and latency.
- **Server-side refusal fallback** (`fallbacks: "default"`) is left out. On the current agent model it only reroutes `cyber` and `frontier_llm` declines, neither plausible for sales briefs, and a silent switch to another model would muddy eval comparisons. Refusals fail loudly instead.
- **Smarter `search_accounts`.** Match on email domain, fuzzy names, and the reverse substring direction (a variant inside the query, e.g. "Pellwick Freight Inc").
- **`search_transcripts` returns full text.** Fine at 2 to 3 short transcripts per account. Revisit (snippets plus a `get_transcript` tool) if transcripts grow.
- **Activity notes.** `activity` is an empty list on every account today. Notes need their own IDs, which needs a source ID convention (e.g. `crm:activity/ACT-001`) added to CLAUDE.md first.
- **Routine-case check.** SPEC's "zero caution flags on routine cases" is not in today's six checks. It needs a definition of which flag types count as caution flags.
- **Cost and latency per run.** Log token usage and wall time per case (MLflow, Oct 9).

## Decisions (Oct 6)

- The lead record goes into the first user message, cited as `crm:lead/L-001`. None of the five SPEC tools fetches a lead.
- `call_context_note` holds one or two sentences on the lead themself and their inbound request (who, what they asked for, when).
- `.env` is read by a 10-line loader in `config.py` rather than adding `python-dotenv`.
- The API key is read from `LEAD_BRIEF_ANTHROPIC_API_KEY` first, then `ANTHROPIC_API_KEY`. Cloud environments strip `ANTHROPIC_API_KEY`, and their API credentials feature never attaches keys to `api.anthropic.com`, so the project-specific variable is the only way to run live in a cloud session. Use a dedicated key with a low spend limit there, since environment variables are readable inside sessions.
- At the 10-call cap, extra calls in the same turn get an error result, and the next request sends `tool_choice: none` with the same `tools` list, so the history stays append-only.
