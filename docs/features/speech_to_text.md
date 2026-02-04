# Speech-to-Text Feature

## Overview
Speech-to-text (STT) enables file-based transcription through the CLI and automatic
Telegram voice message transcription. OpenAI Whisper is the primary provider with
Groq Whisper as the fallback. Transcripts are normalized and routed into the shared
inbox and runtime as user prompts.

## Core Capabilities
- CLI transcription via `cyberagent transcribe <file>`.
- Telegram voice messages are transcribed and recorded as inbox user prompts.
- Provider fallback from OpenAI to Groq.
- Audio format conversion to WAV when the input format is unsupported.
- Low-confidence detection with user-facing warnings.
- Timestamped transcript formatting for long Telegram inbox entries.

## CLI Behavior
- `cyberagent transcribe <file>` prints the normalized transcript to stdout.
- Emits a warning when transcription confidence is low.
- Attempts OpenAI first, then Groq if OpenAI fails.
- Converts unsupported formats to WAV using `ffmpeg`.

## Telegram Behavior
- Voice messages are downloaded, transcribed, and deleted from the local cache.
- If `TELEGRAM_STT_SHOW_TRANSCRIPTION=true`, the transcript is echoed back to the chat.
- Low-confidence transcriptions trigger an additional warning message.
- Inbox entries include Telegram metadata (`telegram_chat_id`, `telegram_message_id`,
  `telegram_file_id`) plus provider/model details.

## Providers and Configuration
CLI transcription requires `OPENAI_API_KEY` and/or `GROQ_API_KEY`.
Default models are OpenAI `whisper-1` and Groq `whisper-large-v3-turbo`.

Telegram transcription configuration:
- `TELEGRAM_STT_PROVIDER` (default `openai`)
- `TELEGRAM_STT_MODEL`
- `TELEGRAM_STT_FALLBACK_PROVIDER`
- `TELEGRAM_STT_FALLBACK_MODEL`
- `TELEGRAM_STT_MAX_DURATION` (seconds, default `300`)
- `TELEGRAM_STT_SHOW_TRANSCRIPTION` (default `true`)
- `TELEGRAM_AUDIO_CACHE_DIR` (default `/tmp/telegram_audio`)

## Skill Integration
The `speech-to-text` skill (`src/tools/skills/speech-to-text/speech_to_text.py`) provides
a standalone CLI tool for transcription with provider and response-format options. It
is used by the CLI executor tests and can be invoked by the tool runner.

## File Map
- CLI: `src/cyberagent/cli/transcribe.py`
- Core STT: `src/cyberagent/stt/transcribe.py`
- Post-processing: `src/cyberagent/stt/postprocess.py`
- Telegram STT: `src/cyberagent/channels/telegram/stt.py`
- Telegram ingestion: `src/cyberagent/channels/telegram/poller.py`
- Telegram webhook: `src/cyberagent/channels/telegram/webhook.py`
- Skill script: `src/tools/skills/speech-to-text/speech_to_text.py`
- Tests: `tests/stt/test_transcribe.py`, `tests/cli/test_cyberagent.py`,
  `tests/channels/test_telegram_stt.py`, `tests/channels/test_telegram_webhook_stt.py`,
  `tests/tools/test_cli_executor_scripts.py`
