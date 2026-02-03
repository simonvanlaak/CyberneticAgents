# Shared Inbox Feature

## Overview
The shared inbox aggregates user prompts, system questions, and system responses from all channels into a single feed. Each entry preserves `channel` and `session_id` so replies are routed deterministically back to the originating channel.

## Entry Types
- `user_prompt`: User input received from any channel.
- `system_question`: Questions raised by System4 or other systems that require a user response.
- `system_response`: Informational system updates delivered to the user.

## Status and Resolution
- `system_question` entries have a `status` of `pending` or `answered`.
- Answered questions store the response text and the answer timestamp.

## CLI Behavior
- `cyberagent inbox` prints user prompts, system questions, and system responses.
- `--answered` includes answered system questions.
- `cyberagent watch` streams new inbox entries as they arrive.

## Storage
- Inbox entries persist to `logs/cli_inbox.json`.
- Legacy inbox state (pending/answered questions) is migrated on read.

## File Map
- Inbox model and storage: `src/cyberagent/channels/inbox.py`
- CLI integration: `src/cyberagent/cli/cyberagent.py`
- User agent recording: `src/agents/user_agent.py`
