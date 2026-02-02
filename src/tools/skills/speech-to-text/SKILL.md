---
name: speech-to-text
description: Transcribe audio files to text using Groq or OpenAI Whisper.
metadata:
  cyberagent:
    tool: speech-to-text
    subcommand: run
    timeout_class: long
input_schema:
  type: object
  properties:
    file:
      type: string
    provider:
      type: string
    model:
      type: string
    language:
      type: string
    response_format:
      type: string
    fallback_provider:
      type: string
    fallback_model:
      type: string
output_schema:
  type: object
  properties:
    text:
      type: string
    segments:
      type: array
    provider:
      type: string
    model:
      type: string
    language:
      type: string
---

Use this skill to transcribe audio files into text. Provide a local file path and
optionally specify a provider, model, and language. When a provider fails, a
fallback provider can be used if configured.

Examples:
- Transcribe with Groq (default):
  {"file": "/tmp/voice.wav"}
- Transcribe with OpenAI:
  {"file": "/tmp/voice.wav", "provider": "openai", "model": "whisper-1"}
- Include verbose segments:
  {"file": "/tmp/voice.wav", "response_format": "verbose_json"}
