from __future__ import annotations

import builtins
import sys
import types
from typing import Any

import pytest
from autogen_ext.models.openai import OpenAIChatCompletionClient

from src.llm_config import LLMConfig
from src.model_factory import (
    _create_mistral_client,
    create_model_client,
    get_available_providers,
    validate_config,
)


def test_get_available_providers_includes_expected() -> None:
    assert set(get_available_providers()) == {"groq", "mistral", "openai"}


def test_validate_config_rejects_invalid_fields() -> None:
    assert validate_config(LLMConfig(provider="", model="m", api_key="k")) is False
    assert validate_config(LLMConfig(provider="other", model="m", api_key="k")) is False
    assert validate_config(LLMConfig(provider="groq", model="m", api_key="")) is False
    assert (
        validate_config(
            LLMConfig(provider="groq", model="", api_key="k", temperature=0.2)
        )
        is False
    )
    assert (
        validate_config(
            LLMConfig(provider="groq", model="m", api_key="k", temperature=-0.1)
        )
        is False
    )
    assert (
        validate_config(
            LLMConfig(provider="groq", model="m", api_key="k", max_tokens=0)
        )
        is False
    )
    assert validate_config(LLMConfig(provider="groq", model="m", api_key="k")) is True


def test_create_model_client_invalid_provider_raises() -> None:
    config = LLMConfig(provider="other", model="m", api_key="k")
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        create_model_client(config)


def test_create_model_client_groq_returns_openai_client() -> None:
    config = LLMConfig(
        provider="groq",
        model="llama-3.3-70b-versatile",
        api_key="test-groq-key",
        base_url="https://example.test/openai",
    )

    client = create_model_client(config)

    assert isinstance(client, OpenAIChatCompletionClient)


def test_create_model_client_mistral_returns_openai_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any):
        if name == "autogen_ext.models.mistral":
            raise ImportError("mistral client not available")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    config = LLMConfig(provider="mistral", model="mistral-small-latest", api_key="k")

    client = create_model_client(config)

    assert isinstance(client, OpenAIChatCompletionClient)


def test_create_model_client_openai_returns_openai_client() -> None:
    config = LLMConfig(
        provider="openai",
        model="gpt-5-nano-2025-08-07",
        api_key="test-openai-key",
        base_url="https://api.openai.com/v1",
    )

    client = create_model_client(config)

    assert isinstance(client, OpenAIChatCompletionClient)


def test_create_mistral_client_uses_native_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    dummy_module = types.ModuleType("autogen_ext.models.mistral")

    class DummyMistralClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    setattr(dummy_module, "MistralChatCompletionClient", DummyMistralClient)
    monkeypatch.setitem(sys.modules, "autogen_ext.models.mistral", dummy_module)

    config = LLMConfig(
        provider="mistral",
        model="mistral-large-latest",
        api_key="test-mistral-key",
        temperature=0.2,
        max_tokens=512,
        top_p=0.8,
        random_seed=7,
        safe_prompt=False,
    )

    client = _create_mistral_client(config)

    assert isinstance(client, DummyMistralClient)
    assert captured["model"] == "mistral-large-latest"
    assert captured["api_key"] == "test-mistral-key"
    assert captured["api_type"] == "mistral"
    assert captured["temperature"] == 0.2
    assert captured["max_tokens"] == 512
    assert captured["top_p"] == 0.8
    assert captured["random_seed"] == 7
    assert captured["safe_prompt"] is False


def test_create_mistral_client_falls_back_to_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any):
        if name == "autogen_ext.models.mistral":
            raise ImportError("mistral client not available")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    config = LLMConfig(provider="mistral", model="mistral-small-latest", api_key="k")
    client = _create_mistral_client(config)

    assert isinstance(client, OpenAIChatCompletionClient)
