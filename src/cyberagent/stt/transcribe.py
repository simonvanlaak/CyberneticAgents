"""English-only speech-to-text transcription with OpenAI primary."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
from typing import Any

import requests

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
OPENAI_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"

DEFAULT_MODELS = {
    "openai": "whisper-1",
    "groq": "whisper-large-v3-turbo",
}
SUPPORTED_AUDIO_SUFFIXES = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    provider: str
    model: str


def transcribe_file(file_path: Path) -> TranscriptionResult:
    """
    Transcribe an audio file in English using OpenAI primary and Groq fallback.

    Args:
        file_path: Path to the audio file to transcribe.

    Returns:
        The transcription result with provider and model metadata.
    """
    prepared_path, cleanup_path = _prepare_audio(file_path)
    providers = ["openai", "groq"]
    last_error: Exception | None = None
    try:
        for provider in providers:
            try:
                model = DEFAULT_MODELS[provider]
                return _transcribe_provider(provider, model, prepared_path)
            except Exception as exc:
                last_error = exc
                continue
    finally:
        if cleanup_path is not None:
            try:
                cleanup_path.unlink()
            except OSError:
                pass
    if last_error:
        raise RuntimeError(str(last_error))
    raise RuntimeError("No transcription providers available.")


def _transcribe_provider(
    provider: str, model: str, file_path: Path
) -> TranscriptionResult:
    endpoint = OPENAI_ENDPOINT if provider == "openai" else GROQ_ENDPOINT
    api_key = _require_key(provider)
    with file_path.open("rb") as handle:
        files = {"file": (file_path.name, handle)}
        data: dict[str, Any] = {
            "model": model,
            "response_format": "text",
            "language": "en",
        }
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            files=files,
            data=data,
            timeout=60,
        )
        response.raise_for_status()
        text = response.text
    return TranscriptionResult(text=text, provider=provider, model=model)


def _require_key(provider: str) -> str:
    env_var = "OPENAI_API_KEY" if provider == "openai" else "GROQ_API_KEY"
    api_key = os.environ.get(env_var)
    if not api_key:
        raise RuntimeError(f"Missing required {env_var} environment variable.")
    return api_key


def _prepare_audio(file_path: Path) -> tuple[Path, Path | None]:
    suffix = file_path.suffix.lower()
    if suffix in SUPPORTED_AUDIO_SUFFIXES:
        return file_path, None
    return _convert_to_wav(file_path)


def _convert_to_wav(file_path: Path) -> tuple[Path, Path]:
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_file.close()
    output_path = Path(temp_file.name)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(file_path), str(output_path)],
        check=True,
    )
    return output_path, output_path
