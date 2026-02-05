from pathlib import Path

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
    monkeypatch.setattr(stt, "get_secret", lambda *_args, **_kwargs: None)

    config = stt.load_config()

    assert config.provider == "openai"
    assert config.language == "en"


def test_load_config_ignores_language_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_STT_LANGUAGE", "es")

    config = stt.load_config()

    assert config.language == "en"


def test_load_config_defaults_to_groq_when_groq_key_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TELEGRAM_STT_PROVIDER", raising=False)
    monkeypatch.delenv("TELEGRAM_STT_MODEL", raising=False)
    monkeypatch.delenv("TELEGRAM_STT_LANGUAGE", raising=False)

    def _fake_get_secret(name: str) -> str | None:
        if name == "GROQ_API_KEY":
            return "groq-key"
        if name == "OPENAI_API_KEY":
            return None
        return None

    monkeypatch.setattr(stt, "get_secret", _fake_get_secret)

    config = stt.load_config()

    assert config.provider == "groq"


def test_describe_transcription_error_for_missing_openai_key() -> None:
    error = RuntimeError("Missing required OPENAI_API_KEY environment variable.")

    message = stt.describe_transcription_error(error)

    assert "OPENAI_API_KEY" in message


def test_describe_transcription_error_for_missing_groq_key() -> None:
    error = RuntimeError("Missing required GROQ_API_KEY environment variable.")

    message = stt.describe_transcription_error(error)

    assert "GROQ_API_KEY" in message


def test_resolve_upload_name_maps_oga_to_ogg(tmp_path: Path) -> None:
    file_path = tmp_path / "voice.oga"
    file_path.write_text("placeholder")

    assert stt._resolve_upload_name(file_path) == "voice.ogg"
