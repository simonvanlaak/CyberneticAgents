# Communication Channels Feature

## Overview
Communication channels define how inbound messages are routed into the runtime and how
replies are delivered back to the originating channel. Each message carries a `channel`
and `session_id`, which together form the canonical session key for routing and inbox
tracking.

## Core Capabilities
- Canonical session key: `<channel>:<session_id>`.
- Reply routing enforcement keeps responses on the origin channel/session.
- Shared inbox entries persist `channel` and `session_id` for deterministic replies.
- CLI and Telegram channels are supported out of the box.

## Channel Models
- CLI defaults: `channel=cli`, `session_id=cli-main`.
- Telegram session key: `telegram:chat-<chat_id>:user-<user_id>`.
- Telegram `/reset` issues a reset session key and sets `reset_session=true`.
- Telegram text metadata: `telegram_chat_id`, `telegram_message_id`.
- Telegram callback metadata: `telegram_chat_id`, `telegram_message_id`,
  `telegram_callback_id`, `telegram_callback_data`.
- Telegram voice metadata: `telegram_chat_id`, `telegram_message_id`, `telegram_file_id`.
- Allowlist/blocklist checks gate inbound traffic before routing.

## Routing and Inbox Behavior
- `MessageRoute` tracks `channel` and `session_id` for every inbound message.
- `build_session_key` produces the canonical `<channel>:<session_id>` form.
- Replies are allowed only when the reply route matches the origin route.
- User prompts, system questions, and system responses are recorded in the shared inbox
  with the same channel/session metadata.

## File Map
- Routing primitives: `src/cyberagent/channels/routing.py`
- Shared inbox: `src/cyberagent/channels/inbox.py`
- User agent routing: `src/agents/user_agent.py`
- Telegram session IDs: `src/cyberagent/channels/telegram/parser.py`
- Telegram ingress: `src/cyberagent/channels/telegram/poller.py`
- Telegram webhook: `src/cyberagent/channels/telegram/webhook.py`
- CLI inbox filters: `src/cyberagent/cli/cyberagent.py`
