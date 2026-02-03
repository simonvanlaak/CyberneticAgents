from __future__ import annotations

import pytest

from src.llm_config import (
    determine_system_type,
    get_model_for_system_type,
    load_llm_config,
)
from src.rbac.system_types import SystemTypes


def test_load_llm_config_groq_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        load_llm_config()


def test_load_llm_config_groq_reads_onepassword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.setattr(
        "src.llm_config.get_secret", lambda *_args, **_kwargs: "vault-groq"
    )

    config = load_llm_config()

    assert config.provider == "groq"
    assert config.api_key == "vault-groq"


def test_load_llm_config_mistral_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mistral")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
    monkeypatch.setenv("LLM_MAX_TOKENS", "1234")
    monkeypatch.setenv("LLM_TOP_P", "0.9")
    monkeypatch.setenv("LLM_RANDOM_SEED", "42")
    monkeypatch.setenv("LLM_SAFE_PROMPT", "false")
    monkeypatch.setenv("MISTRAL_MODEL", "mistral-medium-latest")

    config = load_llm_config()

    assert config.provider == "mistral"
    assert config.api_key == "test-mistral-key"
    assert config.temperature == 0.3
    assert config.max_tokens == 1234
    assert config.top_p == 0.9
    assert config.random_seed == 42
    assert config.safe_prompt is False
    assert config.api_type == "mistral"
    assert config.model == "mistral-medium-latest"


def test_load_llm_config_groq_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("GROQ_BASE_URL", "https://example.test/groq")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-70b")

    config = load_llm_config()

    assert config.provider == "groq"
    assert config.api_key == "test-groq-key"
    assert config.base_url == "https://example.test/groq"
    assert config.model == "llama-3.1-70b"


def test_get_model_for_system_type_mapping_and_fallback() -> None:
    assert (
        get_model_for_system_type(SystemTypes.SYSTEM_4_INTELLIGENCE, "mistral")
        == "mistral-large-latest"
    )
    assert (
        get_model_for_system_type("unknown_system", "groq") == "llama-3.3-70b-versatile"
    )


def test_determine_system_type_defaults_and_matches() -> None:
    assert determine_system_type("root_3control_sys3") == SystemTypes.SYSTEM_3_CONTROL
    assert (
        determine_system_type("root_2coordination_sys2")
        == SystemTypes.SYSTEM_2_COORDINATION
    )
    assert (
        determine_system_type("root_4intelligence_sys4")
        == SystemTypes.SYSTEM_4_INTELLIGENCE
    )
    assert determine_system_type("root_5policy_sys5") == SystemTypes.SYSTEM_5_POLICY
    assert determine_system_type("unknown_agent") == SystemTypes.SYSTEM_1_OPERATIONS


def test_load_llm_config_mistral_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mistral")
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
        load_llm_config()


def test_determine_system_type_system1_match() -> None:
    assert (
        determine_system_type("root_1operations_sys1")
        == SystemTypes.SYSTEM_1_OPERATIONS
    )
