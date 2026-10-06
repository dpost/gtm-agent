"""API key lookup and client wiring. No API calls."""

import anthropic
import pytest

from lead_brief import config
from lead_brief.agent import BriefError, brief_lead


@pytest.fixture
def no_dotenv(monkeypatch):
    """Keep a developer's local .env out of these tests."""
    monkeypatch.setattr(config, "load_env", lambda *args, **kwargs: None)


def test_project_key_wins_over_anthropic_key(monkeypatch):
    monkeypatch.setenv("LEAD_BRIEF_ANTHROPIC_API_KEY", "project-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "generic-key")
    assert config.api_key() == "project-key"


def test_falls_back_to_anthropic_key(monkeypatch):
    monkeypatch.setenv("LEAD_BRIEF_ANTHROPIC_API_KEY", "  ")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "generic-key")
    assert config.api_key() == "generic-key"


def test_no_key_returns_none():
    assert config.api_key() is None


def test_missing_key_fails_loudly_naming_both_variables(no_dotenv):
    with pytest.raises(BriefError, match="LEAD_BRIEF_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY"):
        brief_lead("L-001")


def test_client_gets_the_project_key(monkeypatch, no_dotenv):
    seen = {}

    def capture(**kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop before any request")

    monkeypatch.setattr(anthropic, "Anthropic", capture)
    monkeypatch.setenv("LEAD_BRIEF_ANTHROPIC_API_KEY", "project-key")
    with pytest.raises(RuntimeError, match="stop before any request"):
        brief_lead("L-001")
    assert seen == {"api_key": "project-key"}
