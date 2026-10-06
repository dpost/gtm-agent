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

# Bump these when a prompt or a tool's behavior changes, so eval runs stay comparable.
PROMPT_VERSION = "agent-v1"
TOOL_VERSION = "tools-v1"

# Paths
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
ANSWER_KEY_PATH = DATA_DIR / "answer_key" / "cases.json"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
AGENT_PROMPT_PATH = PROMPTS_DIR / "agent_system.md"


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
