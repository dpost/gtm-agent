# CLAUDE.md

Guidance for Claude Code working in this repo. Read SPEC.md before any task; it is the source of truth. If a request conflicts with SPEC.md, stop and ask.

## What this is

A pre-call brief agent for SDRs, plus the eval harness that measures it. Given a new lead, the agent checks a synthetic CRM, usage scorecard, and call transcripts, then returns a cited brief whose loudness matches the situation: quiet on routine leads, loud on risky ones. The eval harness is as important as the agent.

## Hard rules

1. **Synthetic data only.** Every company, person, and record is invented. Never use real company names. Never paste or recreate code, data, prompts, or internal names from any employer or client.
2. **Prototype, not production.** In code comments, docs, and commit messages, call this a prototype or reference implementation.
3. **No em dashes** in any Markdown, docstring, comment, prompt, or generated text. Use a colon, comma, period, or parentheses.
4. **No agent frameworks.** The tool-use loop is hand-written on the Anthropic Python SDK. Do not add LangChain, LangGraph, LlamaIndex, CrewAI, or similar. Ask before adding any new dependency.
5. **Read-only agent.** No tool writes to the data.
6. **Secrets.** The API key comes from `LEAD_BRIEF_ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEY`, in the environment or a gitignored `.env`; `config.api_key()` checks them in that order. Cloud sessions strip `ANTHROPIC_API_KEY` (Claude Code reserves it for its own login), so use `LEAD_BRIEF_ANTHROPIC_API_KEY` there. Never commit keys, never print them.
7. **Scope.** Check SPEC.md's "Out of scope for v1" before building anything not in the current task. If something would be nice to have, add it to `NOTES.md` under "Later" and keep going.

## Stack

- Python 3.11+. Use `uv` if installed, otherwise `venv` plus `pip install -e .`.
- `anthropic` (Messages API with tool use), `pydantic` (brief schema), `mlflow` (tracking and traces, from the Oct 9 task on), `mcp` (official MCP Python SDK, from the Oct 13 task on), `pytest`.
- Models live in `src/lead_brief/config.py`, never hard-coded elsewhere. Defaults: agent `claude-sonnet-5-5`, judge `claude-sonnet-5-5`.

## Repo layout

```
SPEC.md  CLAUDE.md  README.md  NOTES.md
data/
  answer_key/cases.json        # expected answers, written before the data
  crm/  usage/  transcripts/   # synthetic sources, JSON and .txt
src/lead_brief/
  config.py      # models, paths, prompt and tool version strings
  schema.py      # Brief pydantic model
  data_store.py  # loads data; the five tool functions live here
  tools.py       # tool schemas for the Anthropic API, mapped to data_store
  agent.py       # tool-use loop; brief_lead(lead_id) -> Brief
evals/
  scorers.py     # correctness (code), groundedness, actionability
  run_eval.py    # runs cases, prints and logs results
scripts/         # generate_data.py, check_data.py
mcp_server/      # server.py (Oct 13)
tests/
```

Create folders only when a task needs them.

## Conventions

- **Source IDs** follow `crm:account/ACC-017`, `crm:contact/CON-102`, `crm:opp/OPP-031`, `crm:lead/L-001`, `usage:ACC-017`, `transcript:T-0042`. Every data record carries its own ID so citations can be checked by code.
- **Tool functions** are plain Python with type hints and return plain dicts. The same functions serve the agent loop and, later, the MCP server. Never fork them.
- **Prompts** live in files under `src/lead_brief/prompts/`, each with a version string in `config.py`. Bump the version when a prompt changes, so eval runs stay comparable.
- **Keep it small.** Short modules, no abstraction layers until a second use exists.

## How to work

- Start each task by restating its definition of done and listing the files you expect to touch. Then build.
- Run the code before saying it works. Show the command and the output.
- Fast tests (`pytest`) must not call the API. Anything that calls the API is a script or an eval run.
- When a task is done, summarize what changed, what's next, and anything you deferred to `NOTES.md`.
- If you are about to spend more than a few minutes on something outside the current task, stop and ask.

## Commands

```
python -m lead_brief.agent L-001     # print one brief
python -m evals.run_eval             # run cases and print scores
pytest                               # fast tests, no API calls
```
