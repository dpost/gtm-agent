"""Models, paths, and version strings for the prototype. Nothing else hard-codes these."""

import os
from pathlib import Path

AS_OF_DATE = "2026-10-06"

# Models
AGENT_MODEL = "claude-sonnet-5-5"
JUDGE_MODEL = "claude-sonnet-5-5"
AGENT_EFFORT = "medium"
AGENT_MAX_TOKENS = 16000
MAX_TOOL_CALLS = 10
TRANSCRIPT_MODEL = "claude-sonnet-5-5"  # writes transcript prose in scripts/generate_data.py
TRANSCRIPT_EFFORT = "low"

# Bump these when a prompt or a tool's behavior changes, so eval runs stay comparable.
PROMPT_VERSION = "agent-v1"
TOOL_VERSION = "tools-v1"

# Paths
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
ANSWER_KEY_PATH = DATA_DIR / "answer_key" / "cases.json"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
AGENT_PROMPT_PATH = PROMPTS_DIR / "agent_system.md"
REPORTS_DIR = REPO_ROOT / "reports"  # HTML eval reports, gitignored


# Cloud sessions strip ANTHROPIC_API_KEY (Claude Code reserves it for its own login),
# so the project-specific name is checked first. ANTHROPIC_API_KEY still works locally.
API_KEY_ENV_VARS = ("LEAD_BRIEF_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")


def api_key() -> str | None:
    """The first non-empty key named in API_KEY_ENV_VARS, or None."""
    for name in API_KEY_ENV_VARS:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def load_env(path: Path = REPO_ROOT / ".env") -> None:
    """Read KEY=VALUE lines from a gitignored .env into os.environ, without overriding."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
