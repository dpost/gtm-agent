"""Hand-written tool-use loop on the Anthropic SDK: brief_lead(lead_id) -> Brief.

Prototype. Read-only: no tool writes to the data.
Usage: python -m lead_brief.agent L-001
"""

import json
import logging
import sys

import anthropic
from pydantic import ValidationError

from lead_brief import config, data_store
from lead_brief.schema import Brief
from lead_brief.tools import TOOLS, run_tool

log = logging.getLogger(__name__)


class BriefError(RuntimeError):
    """The agent could not produce a valid brief."""


def system_prompt() -> str:
    schema = json.dumps(Brief.model_json_schema(), indent=2)
    prompt = config.AGENT_PROMPT_PATH.read_text(encoding="utf-8")
    return prompt.replace("{brief_schema}", schema).replace("{max_tool_calls}", str(config.MAX_TOOL_CALLS))


def lead_message(lead: dict) -> str:
    return (
        f"Today is {config.AS_OF_DATE}. Prepare a pre-call brief for this inbound lead.\n\n"
        f"<lead>\n{json.dumps(lead, indent=2)}\n</lead>"
    )


def parse_brief(text: str) -> Brief:
    """Validate the model's final JSON, tolerating code fences or stray prose around the object."""
    start, end = text.find("{"), text.rfind("}")
    return Brief.model_validate_json(text[start : end + 1] if start != -1 else text)


def _call(client, system: str, messages: list, tool_choice: str):
    """One Messages API request. Appends the assistant turn to `messages` unchanged (append-only history)."""
    response = client.messages.create(
        model=config.AGENT_MODEL,
        max_tokens=config.AGENT_MAX_TOKENS,
        thinking={"type": "adaptive"},
        output_config={"effort": config.AGENT_EFFORT},
        system=system,
        tools=TOOLS,  # same list on every request; only tool_choice changes
        tool_choice={"type": tool_choice},
        cache_control={"type": "ephemeral"},  # caches the growing prefix across loop turns
        messages=messages,
    )
    if response.stop_reason == "refusal":
        raise BriefError(f"Model refused: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise BriefError("Response hit max_tokens before the brief was finished.")
    messages.append({"role": "assistant", "content": response.content})
    return response


def _text(response) -> str:
    return "".join(block.text for block in response.content if block.type == "text")


def brief_lead(lead_id: str, client=None, trace: list | None = None) -> Brief:
    """Run the agent for one lead and return a validated Brief. Raises BriefError on failure.

    If `trace` is a list, each tool call (with its result) and validation retry is appended to it as a dict,
    for eval reports.
    """
    trace = [] if trace is None else trace
    lead = data_store.get_lead(lead_id)
    if client is None:
        config.load_env()
        key = config.api_key()
        if key is None:
            names = " or ".join(config.API_KEY_ENV_VARS)
            raise BriefError(f"No API key found. Set {names} in the environment or a gitignored .env.")
        client = anthropic.Anthropic(api_key=key)
    system = system_prompt()
    messages = [{"role": "user", "content": lead_message(lead)}]
    tool_calls = 0

    response = _call(client, system, messages, "auto")
    while response.stop_reason == "tool_use":
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if tool_calls >= config.MAX_TOOL_CALLS:
                trace.append({"kind": "skipped", "name": block.name, "input": block.input})
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Tool call budget used up; this call was not run.",
                    "is_error": True,
                })
                continue
            tool_calls += 1
            log.info("tool %d/%d: %s %s", tool_calls, config.MAX_TOOL_CALLS, block.name, json.dumps(block.input))
            content, is_error = run_tool(block.name, block.input)
            trace.append({
                "kind": "tool", "name": block.name, "input": block.input, "output": content, "is_error": is_error,
            })
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error})

        out_of_budget = tool_calls >= config.MAX_TOOL_CALLS
        if out_of_budget:
            results.append({
                "type": "text",
                "text": f"You have used all {config.MAX_TOOL_CALLS} tool calls. Write the final brief JSON now.",
            })
        messages.append({"role": "user", "content": results})
        response = _call(client, system, messages, "none" if out_of_budget else "auto")

    text = _text(response)
    try:
        return parse_brief(text)
    except ValidationError as first_error:
        log.warning("Brief failed validation; retrying once.\n%s", first_error)
        trace.append({"kind": "retry", "error": str(first_error), "output": text})
        messages.append({
            "role": "user",
            "content": f"That brief failed validation:\n{first_error}\n\nReply with only the corrected JSON object.",
        })
        text = _text(_call(client, system, messages, "none"))
        try:
            return parse_brief(text)
        except ValidationError as second_error:
            raise BriefError(
                f"Brief failed validation twice.\nLast error: {second_error}\nLast output:\n{text}"
            ) from second_error


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)
    logging.getLogger("lead_brief").setLevel(logging.INFO)
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m lead_brief.agent LEAD_ID", file=sys.stderr)
        return 2
    brief = brief_lead(args[0])
    print(brief.render())
    print()
    print(brief.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
