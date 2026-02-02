from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.channels.telegram import stt as telegram_stt


def test_transcribe_file_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"fake")

    config = telegram_stt.TelegramSTTConfig(
        provider="groq",
        model="whisper-large-v3-turbo",
        language=None,
        fallback_provider="openai",
        fallback_model="whisper-1",
        max_duration_seconds=300,
        show_transcription=True,
    )

    calls: list[tuple[str, str]] = []

    def _fake_transcribe_provider(
        provider: str, model: str, file_path: Path, language: str | None
    ) -> telegram_stt.TranscriptionResult:
        calls.append((provider, model))
        if provider == "groq":
            raise RuntimeError("groq down")
        return telegram_stt.TranscriptionResult(
            text="hello",
            provider=provider,
            model=model,
            language="en",
            segments=[],
        )

    monkeypatch.setattr(telegram_stt, "_transcribe_provider", _fake_transcribe_provider)

    result = telegram_stt.transcribe_file(audio_path, config)

    assert calls == [("groq", "whisper-large-v3-turbo"), ("openai", "whisper-1")]
    assert result.text == "hello"
    assert result.provider == "openai"
