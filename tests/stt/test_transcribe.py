from __future__ import annotations

from pathlib import Path

import pytest
import requests

from typing import TypedDict

from src.cyberagent.stt import transcribe


class _Call(TypedDict):
    url: str
    data: dict[str, str]
    headers: dict[str, str]


class _Response:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")


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
        return _Response("hello from groq")

    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setattr(transcribe.requests, "post", fake_post)

    result = transcribe.transcribe_file(audio_path)

    assert result.text == "hello from groq"
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
        return _Response("hello from openai")

    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(transcribe.requests, "post", fake_post)

    result = transcribe.transcribe_file(audio_path)

    assert result.text == "hello from openai"
    assert result.provider == "openai"
