import pytest

from src.cyberagent.channels.telegram import stt


def test_require_key_reads_onepassword(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(stt, "get_secret", lambda *_args, **_kwargs: "vault-key")

    assert stt._require_key("groq") == "vault-key"


def test_load_config_defaults_to_openai_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TELEGRAM_STT_PROVIDER", raising=False)
    monkeypatch.delenv("TELEGRAM_STT_MODEL", raising=False)
    monkeypatch.delenv("TELEGRAM_STT_LANGUAGE", raising=False)

    config = stt.load_config()

    assert config.provider == "openai"
    assert config.language == "en"


def test_load_config_ignores_language_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_STT_LANGUAGE", "es")

    config = stt.load_config()

    assert config.language == "en"
