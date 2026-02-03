from __future__ import annotations

from pathlib import Path

import pytest
import requests

from typing import TypedDict, cast

from src.cyberagent.stt import transcribe


class _Call(TypedDict):
    url: str
    data: dict[str, str]
    headers: dict[str, str]


class _Response:
    def __init__(
        self,
        text: str,
        status_code: int = 200,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.text = text
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self) -> dict[str, object]:
        return self._payload or {}


def test_transcribe_file_uses_openai_then_groq_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")
    calls: list[_Call] = []

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        files: dict[str, object],
        data: dict[str, str],
        timeout: int,
    ) -> _Response:
        calls.append({"url": url, "data": data, "headers": headers})
        if url == transcribe.OPENAI_ENDPOINT:
            return _Response("fail", status_code=500)
        return _Response(
            "hello from groq",
            payload={"text": "hello from groq", "segments": []},
        )

    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setattr(transcribe.requests, "post", fake_post)

    result = transcribe.transcribe_file(audio_path)

    assert result.text == "Hello from groq."
    assert result.provider == "groq"
    assert calls[0]["url"] == transcribe.OPENAI_ENDPOINT
    assert calls[1]["url"] == transcribe.GROQ_ENDPOINT
    assert calls[0]["data"]["language"] == "en"
    assert calls[1]["data"]["language"] == "en"


def test_transcribe_file_uses_openai_primary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        files: dict[str, object],
        data: dict[str, str],
        timeout: int,
    ) -> _Response:
        assert url == transcribe.OPENAI_ENDPOINT
        return _Response(
            "hello from openai",
            payload={"text": "hello from openai", "segments": []},
        )

    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(transcribe.requests, "post", fake_post)

    result = transcribe.transcribe_file(audio_path)

    assert result.text == "Hello from openai."
    assert result.provider == "openai"


def test_transcribe_file_converts_unsupported_audio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    audio_path = tmp_path / "audio.txt"
    audio_path.write_text("not audio", encoding="utf-8")
    recorded: dict[str, object] = {}

    def fake_run(args: list[str], check: bool) -> None:
        recorded["ffmpeg_args"] = args
        output_path = Path(args[-1])
        output_path.write_bytes(b"wav")

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        files: dict[str, object],
        data: dict[str, str],
        timeout: int,
    ) -> _Response:
        file_entry = cast(tuple[object, object], files["file"])
        recorded["sent_file"] = str(file_entry[0])
        return _Response(
            "converted audio",
            payload={"text": "converted audio", "segments": []},
        )

    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(transcribe.subprocess, "run", fake_run)
    monkeypatch.setattr(transcribe.requests, "post", fake_post)

    result = transcribe.transcribe_file(audio_path)

    assert result.text == "Converted audio."
    sent_file = cast(str, recorded.get("sent_file"))
    ffmpeg_args = cast(list[str], recorded.get("ffmpeg_args"))
    assert sent_file.endswith(".wav")
    output_path = Path(ffmpeg_args[-1])
    assert not output_path.exists()


def test_transcribe_file_flags_low_confidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        files: dict[str, object],
        data: dict[str, str],
        timeout: int,
    ) -> _Response:
        return _Response(
            "noisy audio",
            payload={
                "text": "noisy audio",
                "segments": [{"start": 0.0, "text": "noisy", "no_speech_prob": 0.95}],
            },
        )

    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(transcribe.requests, "post", fake_post)

    result = transcribe.transcribe_file(audio_path)

    assert result.low_confidence is True


def test_transcribe_file_keeps_single_word_without_period(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        files: dict[str, object],
        data: dict[str, str],
        timeout: int,
    ) -> _Response:
        return _Response(
            "deploy",
            payload={"text": "deploy", "segments": []},
        )

    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(transcribe.requests, "post", fake_post)

    result = transcribe.transcribe_file(audio_path)

    assert result.text == "Deploy"
