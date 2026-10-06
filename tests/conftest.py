import pytest


@pytest.fixture(autouse=True)
def no_api_calls(monkeypatch):
    """Fast tests must never reach the API: constructing a real client fails the test."""
    import anthropic

    def refuse(*args, **kwargs):
        raise RuntimeError("tests must not call the Anthropic API; pass a fake client")

    monkeypatch.setattr(anthropic, "Anthropic", refuse)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
