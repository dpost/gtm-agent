# Lead Brief Agent: Spec

Locked Oct 5, 2026. Changes after lock go in the Change Log at the bottom, with a reason.

## The claim

> Reps are doing a hundred things at once, so an agent has to stay quiet on routine leads and get loud on risky ones.

Results line, filled in after the Oct 13 run: "On 40 synthetic leads, the share of briefs a rep could act on alone went from X% to Y% after [one change]."

## User and workflow

An SDR gets a new inbound lead. Before dialing, they need one answer: do we already have a relationship with this company, and what do I need to know before I call?

- **Useful means:** the rep preps from one place instead of three (CRM, call recorder, usage dashboard).
- **Success on a routine lead:** a short brief the rep can skim in seconds. Skimming is the system working.
- **Failure:** crying wolf on routine leads, or burying the signal on risky ones. Both teach reps to ignore the agent.

## Synthetic world

Seller: **Larkspur Analytics** (fictional), a mid-market B2B analytics SaaS with seat-based licensing. Every company and person is invented. No real companies, no data from any employer.

| Source | Contents |
|---|---|
| CRM | Accounts with parent/child hierarchy and name variants; leads; contacts with role tags and employment history; opportunities (owner, stage, amount, close date, closed-lost reason); rep-entered MEDDPICC fields with last-updated dates; activity notes |
| Usage scorecard | 12 weeks per customer account: licensed seats, active seats (utilization), 3 to 4 feature adoption counts, health score |
| Call transcripts | 2 to 3 per account with history, plain text, each with an ID |

**Answer key first, data second.** Each case's expected answer is written before its data. Code generates all numbers; an LLM writes only transcript prose; `check_data.py` verifies every planted fact landed.

### Case mix (40 leads)

| Cases | Situation | Alert level | The brief should |
|---|---|---|---|
| 8 | Net new, no relationship | routine | Say so plainly, invent nothing |
| 8 | Healthy customer in another department | heads_up | Surface the warm reference |
| 6 | At-risk customer in another department | caution | Warn the rep off, say why |
| 6 | Prior closed-lost deal | caution | Surface the objection from the transcript |
| 6 | Job changer: lead was a contact at another customer | heads_up | Flag the existing relationship |
| 6 | Conflict: open opp owned by another rep, or a stale CRM contact | caution | Flag the conflict and who to talk to |

Company name variants, subsidiaries, and look-alike unrelated companies are spread across all rows.

## The agent

- **Input:** `lead_id`. **Output:** a structured brief (validated JSON) plus rendered text.
- **Brief fields:** `alert_level`, `relationship_status` (one of the six situations), `related_account_ids`, `headline` (the one line the rep must see first), `flags` (each with `type`, `claim`, `source_ids`), `summary`, `call_context_note`, `recommended_action`.
- **Every claim cites a source ID**, e.g. `crm:account/ACC-017`, `usage:ACC-017`, `transcript:T-0042`.
- **Read-only.** A hand-written tool-use loop on the Anthropic Python SDK. No agent framework.

### Tools (plain Python functions, later wrapped by MCP)

| Tool | Returns |
|---|---|
| `search_accounts(name)` | Matching account IDs, with hierarchy and name variants |
| `get_account(account_id)` | CRM record, contacts, opps, MEDDPICC with dates, activity |
| `get_usage(account_id)` | The 12-week scorecard |
| `search_transcripts(query)` | Transcript hits by account or contact, with IDs |
| `find_person(name_or_email)` | Every contact record for a person, across accounts |
| `brief_lead(lead_id)` | The whole agent as one call (MCP only) |

## The eval

Three scorers per case:

1. **Correctness (code):** `relationship_status` and `alert_level` match the key; planted flags found; related account IDs correct; zero caution flags on routine cases.
2. **Groundedness:** code checks every cited ID exists; an LLM judge rates each claim against its cited record as supported, partial, or unsupported.
3. **Actionability (LLM judge, pass/fail):** does the brief's loudness match the situation? Routine stays short with no manufactured urgency. Caution puts the risk and what to do differently in the headline. Heads-up names the opportunity and its source.

- **Headline metric:** share of cases passing all three.
- **Named failure modes:** false alarm, buried signal.
- **Also logged:** cost and latency per run.
- **Judge calibration:** the author hand-labels 15 briefs as right, too loud, or too quiet; the README reports judge agreement.
- **Tracking:** MLflow, local. One run per eval pass, with model, prompt version, and tool version as params; scores as metrics; a per-case results table as an artifact; traces via MLflow's Anthropic autolog.

## MCP server

The five data tools plus `brief_lead`, built on the official MCP Python SDK over stdio. Demo client: Claude Desktop. In a real deployment this would live where lead handoffs already happen (Slack); the MCP layer is what makes the surface swappable.

## Out of scope for v1

Web search, writing back to the CRM (including MEDDPICC updates), Slack, CSM and AE call types, any custom UI, hosting, auth.

## Milestones (done means the checkpoint is met)

| Date | Checkpoint |
|---|---|
| Tue Oct 6 | One hand-written case, end to end in plain Python, correctness score printed |
| Fri Oct 9 | 40 generated cases, all three scorers, baseline in MLflow |
| Sat Oct 10 to Sun Oct 11 | Buffer, not new scope (judge calibration labels if not done) |
| Tue Oct 13 | MCP server live in Claude Desktop, plus one change that measurably moves the score |
| Thu Oct 15 | README, results table, 2-minute demo, case study |
| Fri Oct 16 | Repo public |

## Guardrails

Synthetic data only. Nothing from any former employer: no code, data, prompts, or internal names. Built on the author's own time and accounts. Described as a prototype or reference implementation, never as production software. No em dashes in any public text.

## Change Log

- Oct 5: spec locked.
