# Communication Channels

## Goal
Define the channel and session model used for routing inbound triggers and delivering replies.

## Channel Model
Each inbound trigger must include `channel` and `session_id`. This route is preserved across
the shared inbox so replies are sent back to the correct channel/session.

### Canonical Session Key
`<channel>:<session_id>`

## Inbox Integration
All inbound user prompts, system questions, and system responses are recorded in the shared inbox.
Entries must preserve `channel` and `session_id`.

## Telegram Channel
Telegram is the primary non-CLI channel and supports polling and webhook modes.

### Session Model
Session key: `telegram:chat-<chat_id>:user-<user_id>`

### Inbound Trigger Types
Text messages:
- Required metadata: `channel`, `session_id`, `telegram_chat_id`, `telegram_message_id`

Callback queries:
- Required metadata: `channel`, `session_id`, `telegram_chat_id`, `telegram_message_id`,
  `telegram_callback_id`, `telegram_callback_data`

Voice messages:
- Voice is transcribed to text before routing.
- Required metadata: `channel`, `session_id`, `telegram_chat_id`, `telegram_message_id`,
  `telegram_file_id`

Reset:
- `/reset` issues a new session id and sets `reset_session` to `"true"`.

### Access Control
Allowlist/blocklist for chats and users applies to inbound triggers. Unauthorized traffic receives
an explicit rejection and is not forwarded.

### Delivery Modes
Webhook is preferred when configured. Polling is the fallback.

## CLI Channel
CLI uses the default route:
- `channel`: `cli`
- `session_id`: `cli-main`

## References
See docs/features/telegram_integration.md
See docs/features/shared_inbox.md
