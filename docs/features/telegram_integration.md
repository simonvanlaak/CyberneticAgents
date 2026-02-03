# Telegram Integration Feature

## Overview
Telegram integration provides a direct communication channel between users and CyberneticAgents. It supports polling or webhook delivery, inbound text messages and callbacks, and outbound replies. Sessions are keyed by chat and user to preserve continuity and isolate conversations.

## Core Capabilities
- **Inbound text**: Text messages are routed into the runtime with channel/session metadata.
- **Outbound replies**: Responses go back to the originating Telegram chat.
- **Commands**: `/start`, `/help`, `/reset` are supported.
- **Webhook + polling**: Webhook is preferred when configured; polling is the fallback.
- **Allowlist/blocklist**: Optional chat/user allow and block lists.
- **Inline keyboards**: Callback queries are parsed and forwarded to the runtime.
- **Shared inbox**: Telegram user prompts, system questions, and system responses are recorded in the shared inbox with `channel=telegram` and the Telegram session id.

## Session Model
- Session key: `telegram:chat-<chat_id>:user-<user_id>`
- `/reset` issues a new session key using a reset token.

## Configuration
Required:
- `TELEGRAM_BOT_TOKEN` (stored in 1Password as `TELEGRAM_BOT_TOKEN` → `credential`)

Optional:
- `TELEGRAM_WEBHOOK_URL`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_WEBHOOK_HOST` (default `0.0.0.0`)
- `TELEGRAM_WEBHOOK_PORT` (default `8080`)
- `TELEGRAM_ALLOWED_CHAT_IDS` (comma-separated)
- `TELEGRAM_ALLOWED_USER_IDS` (comma-separated)
- `TELEGRAM_BLOCKED_CHAT_IDS` (comma-separated)
- `TELEGRAM_BLOCKED_USER_IDS` (comma-separated)

## Local Verification
If you are using polling (no `TELEGRAM_WEBHOOK_URL`), inbound traffic should appear in logs:
```bash
cyberagent logs --level INFO | rg -n "telegram" -i
```

## Inline Keyboard Example
To present inline buttons, send a message with an inline keyboard payload. Callback data will be forwarded into the runtime as a user message.

```python
from src.cyberagent.channels.telegram.outbound import send_message_with_inline_keyboard

send_message_with_inline_keyboard(
    chat_id=123456789,
    text="Approve the proposal?",
    buttons=[
        ("Approve", "approve"),
        ("Reject", "reject"),
    ],
)
```

When the user taps a button:
- Telegram sends a `callback_query`
- The system forwards `callback_query.data` as the user message content
- Metadata includes `telegram_callback_id` and `telegram_callback_data`

## File Map
- `src/cyberagent/channels/telegram/client.py`
- `src/cyberagent/channels/telegram/poller.py`
- `src/cyberagent/channels/telegram/webhook.py`
- `src/cyberagent/channels/telegram/parser.py`
- `src/cyberagent/channels/telegram/outbound.py`
- `src/cyberagent/cli/headless.py`
