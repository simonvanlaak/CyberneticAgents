#!/usr/bin/env python3
"""Speech-to-text CLI wrapper for Groq/OpenAI Whisper."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterable

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
OPENAI_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"

DEFAULT_MODELS = {
    "groq": "whisper-large-v3-turbo",
    "openai": "whisper-1",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Speech-to-text transcription CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Transcribe an audio file.")
    run_parser.add_argument("--file", required=True, help="Path to audio file.")
    run_parser.add_argument(
        "--provider",
        choices=("groq", "openai"),
        default="groq",
        help="Transcription provider.",
    )
    run_parser.add_argument("--model", default=None, help="Model name.")
    run_parser.add_argument(
        "--language",
        default=None,
        help="Language code (e.g., en, es).",
    )
    run_parser.add_argument(
        "--response-format",
        choices=("text", "json", "verbose_json"),
        default="text",
        help="Response format from the provider.",
    )
    run_parser.add_argument(
        "--fallback-provider",
        choices=("groq", "openai"),
        default=None,
        help="Fallback provider if the primary fails.",
    )
    run_parser.add_argument("--fallback-model", default=None, help="Fallback model.")
    return parser


def _require_key(provider: str) -> str:
    env_var = "GROQ_API_KEY" if provider == "groq" else "OPENAI_API_KEY"
    api_key = os.environ.get(env_var)
    if not api_key:
        raise SystemExit(f"Missing required {env_var} environment variable.")
    return api_key


def _provider_sequence(primary: str, fallback: str | None) -> list[str]:
    sequence = [primary]
    if fallback and fallback != primary:
        sequence.append(fallback)
    return sequence


def _resolve_model(provider: str, model: str | None) -> str:
    return model or DEFAULT_MODELS[provider]


def _request_transcription(
    *,
    endpoint: str,
    api_key: str,
    file_path: Path,
    model: str,
    language: str | None,
    response_format: str,
) -> dict[str, Any]:
    import requests

    with file_path.open("rb") as handle:
        files = {"file": (file_path.name, handle)}
        data: dict[str, Any] = {
            "model": model,
            "response_format": response_format,
        }
        if language:
            data["language"] = language
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.post(endpoint, headers=headers, files=files, data=data)
        response.raise_for_status()

        if response_format == "text":
            return {"text": response.text}
        payload = response.json()
        if not isinstance(payload, dict):
            return {"text": str(payload)}
        return payload


def _transcribe_with_fallback(
    *,
    file_path: Path,
    providers: Iterable[str],
    primary_model: str,
    fallback_model: str | None,
    language: str | None,
    response_format: str,
) -> dict[str, Any]:
    provider_list = list(providers)
    last_error: Exception | None = None
    for index, provider in enumerate(provider_list):
        try:
            api_key = _require_key(provider)
            endpoint = GROQ_ENDPOINT if provider == "groq" else OPENAI_ENDPOINT
            model = primary_model if index == 0 else fallback_model
            if model is None:
                model = _resolve_model(provider, None)
            payload = _request_transcription(
                endpoint=endpoint,
                api_key=api_key,
                file_path=file_path,
                model=model,
                language=language,
                response_format=response_format,
            )
            text = (
                payload.get("text", "") if isinstance(payload, dict) else str(payload)
            )
            segments = []
            if isinstance(payload, dict) and "segments" in payload:
                segments = payload.get("segments") or []
            language_value = None
            if isinstance(payload, dict):
                language_value = payload.get("language")
            return {
                "text": text,
                "segments": segments,
                "provider": provider,
                "model": model,
                "language": language_value or language,
            }
        except SystemExit:
            raise
        except Exception as exc:  # pragma: no cover - exercised via fallback
            last_error = exc
            continue

    if last_error:
        raise SystemExit(str(last_error))
    raise SystemExit("No transcription providers available.")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command != "run":
        raise SystemExit(f"Unsupported command: {args.command}")

    file_path = Path(args.file)
    if not file_path.exists():
        raise SystemExit(f"Audio file not found: {file_path}")

    providers = _provider_sequence(args.provider, args.fallback_provider)
    result = _transcribe_with_fallback(
        file_path=file_path,
        providers=providers,
        primary_model=_resolve_model(args.provider, args.model),
        fallback_model=args.fallback_model,
        language=args.language,
        response_format=args.response_format,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
