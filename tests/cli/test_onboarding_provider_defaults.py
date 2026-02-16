from __future__ import annotations

import pytest

from src.cyberagent.cli import onboarding as onboarding_cli


def test_collect_technical_onboarding_state_defaults_to_openai_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    state = onboarding_cli._collect_technical_onboarding_state()

    assert state["llm_provider"] == "openai"
