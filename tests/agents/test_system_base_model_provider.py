from __future__ import annotations

from autogen_core import AgentId

from src.agents import system_base as system_base_module


def test_get_model_client_uses_openai_provider(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setattr(system_base_module, "OpenAIChatCompletionClient", DummyClient)
    monkeypatch.setattr(
        system_base_module, "get_secret", lambda name: "test-openai-key"
    )

    system_base_module.get_model_client(AgentId.from_str("System3/root"), False)

    assert captured["model"] == "gpt-5-nano-2025-08-07"
    assert captured["api_key"] == "test-openai-key"
    assert captured["base_url"] == "https://api.openai.com/v1"


def test_get_model_client_defaults_to_openai_provider(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setattr(system_base_module, "OpenAIChatCompletionClient", DummyClient)
    monkeypatch.setattr(
        system_base_module,
        "get_secret",
        lambda name: "test-openai-key" if name == "OPENAI_API_KEY" else "",
    )

    system_base_module.get_model_client(AgentId.from_str("System3/root"), False)

    assert captured["model"] == "gpt-5-nano-2025-08-07"
    assert captured["api_key"] == "test-openai-key"
    assert captured["base_url"] == "https://api.openai.com/v1"
