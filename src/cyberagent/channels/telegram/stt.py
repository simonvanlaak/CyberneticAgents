from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests

from src.cyberagent.channels.telegram.client import TelegramClient
from src.cyberagent.secrets import get_secret
from src.cyberagent.stt.postprocess import normalize_transcript

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
OPENAI_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"

DEFAULT_MODELS = {
    "openai": "whisper-1",
    "groq": "whisper-large-v3-turbo",
}


@dataclass(frozen=True)
class TelegramSTTConfig:
    provider: str
    model: str
    language: str | None
    fallback_provider: str | None
    fallback_model: str | None
    max_duration_seconds: int
    show_transcription: bool


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    provider: str
    model: str
    language: str | None
    segments: list[dict[str, object]]
    low_confidence: bool = False


def load_config() -> TelegramSTTConfig:
    provider = _resolve_provider()
    model = os.environ.get("TELEGRAM_STT_MODEL") or DEFAULT_MODELS.get(
        provider, "whisper-1"
    )
    fallback_provider = os.environ.get("TELEGRAM_STT_FALLBACK_PROVIDER")
    fallback_model = os.environ.get("TELEGRAM_STT_FALLBACK_MODEL")
    language = "en"
    max_duration_raw = os.environ.get("TELEGRAM_STT_MAX_DURATION", "300")
    try:
        max_duration_seconds = int(max_duration_raw)
    except ValueError:
        max_duration_seconds = 300
    show_transcription = os.environ.get("TELEGRAM_STT_SHOW_TRANSCRIPTION", "true")
    return TelegramSTTConfig(
        provider=provider,
        model=model,
        language=language,
        fallback_provider=fallback_provider,
        fallback_model=fallback_model,
        max_duration_seconds=max_duration_seconds,
        show_transcription=str(show_transcription).lower() not in {"0", "false", "no"},
    )


def _resolve_provider() -> str:
    raw_provider = os.environ.get("TELEGRAM_STT_PROVIDER")
    if raw_provider:
        return raw_provider.lower()
    groq_key = get_secret("GROQ_API_KEY")
    openai_key = get_secret("OPENAI_API_KEY")
    if groq_key and not openai_key:
        return "groq"
    if openai_key:
        return "openai"
    if groq_key:
        return "groq"
    return "openai"


def get_cache_dir() -> Path:
    cache_dir = Path(os.environ.get("TELEGRAM_AUDIO_CACHE_DIR", "/tmp/telegram_audio"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def transcribe_voice_message(
    client: TelegramClient,
    file_id: str,
    config: TelegramSTTConfig,
    cache_dir: Path,
) -> TranscriptionResult:
    file_path = client.get_file_path(file_id)
    suffix = Path(file_path).suffix or ".ogg"
    safe_name = file_id.replace("/", "_")
    local_path = cache_dir / f"{safe_name}{suffix}"
    client.download_file(file_path, local_path)
    try:
        return transcribe_file(local_path, config)
    finally:
        try:
            local_path.unlink()
        except OSError:
            pass


def transcribe_file(
    file_path: Path,
    config: TelegramSTTConfig,
) -> TranscriptionResult:
    providers = [config.provider]
    if config.fallback_provider and config.fallback_provider != config.provider:
        providers.append(config.fallback_provider)
    last_error: Exception | None = None
    for provider in providers:
        try:
            model = (
                config.model
                if provider == config.provider
                else config.fallback_model or DEFAULT_MODELS.get(provider, "whisper-1")
            )
            return _transcribe_provider(provider, model, file_path, config.language)
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise RuntimeError(str(last_error))
    raise RuntimeError("No transcription providers available.")


def _transcribe_provider(
    provider: str,
    model: str,
    file_path: Path,
    language: str | None,
) -> TranscriptionResult:
    endpoint = GROQ_ENDPOINT if provider == "groq" else OPENAI_ENDPOINT
    api_key = _require_key(provider)
    with file_path.open("rb") as handle:
        files = {"file": (file_path.name, handle)}
        data: dict[str, object] = {"model": model, "response_format": "verbose_json"}
        if language:
            data["language"] = language
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            files=files,
            data=data,
            timeout=60,
        )
        response.raise_for_status()
        payload = _parse_payload(response)
        text = (
            str(payload.get("text", "")) if isinstance(payload, dict) else response.text
        )
        text = normalize_transcript(text)
        segments = _parse_segments(payload.get("segments")) if payload else []
    return TranscriptionResult(
        text=text,
        provider=provider,
        model=model,
        language=language,
        segments=segments,
        low_confidence=_is_low_confidence(segments),
    )


def _require_key(provider: str) -> str:
    env_var = "GROQ_API_KEY" if provider == "groq" else "OPENAI_API_KEY"
    api_key = get_secret(env_var)
    if not api_key:
        raise RuntimeError(f"Missing required {env_var} environment variable.")
    return api_key


def describe_transcription_error(exc: Exception) -> str:
    message = str(exc)
    if "Missing required OPENAI_API_KEY" in message:
        return (
            "Transcription is not configured. Set OPENAI_API_KEY or set "
            "TELEGRAM_STT_PROVIDER=groq with GROQ_API_KEY."
        )
    if "Missing required GROQ_API_KEY" in message:
        return (
            "Transcription is not configured. Set GROQ_API_KEY or set "
            "TELEGRAM_STT_PROVIDER=openai with OPENAI_API_KEY."
        )
    return "Could not transcribe voice message."


def _parse_payload(response: requests.Response) -> dict[str, object]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_segments(raw: object) -> list[dict[str, object]]:
    if isinstance(raw, list):
        return [segment for segment in raw if isinstance(segment, dict)]
    return []


def _is_low_confidence(segments: list[dict[str, object]]) -> bool:
    for segment in segments:
        no_speech_prob = segment.get("no_speech_prob")
        avg_logprob = segment.get("avg_logprob")
        if isinstance(no_speech_prob, (int, float)) and no_speech_prob >= 0.6:
            return True
        if isinstance(avg_logprob, (int, float)) and avg_logprob <= -1.0:
            return True
    return False
