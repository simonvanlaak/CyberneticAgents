# Triggers
## Goal
The system needs to receive triggers from the environment (e.g., messaging channels) and route
them to the appropriate system.

## Dependencies
Depends on docs/product_requirements/communication_channels.md
See docs/features/telegram_integration.md
See docs/features/shared_inbox.md

## Notes
Some external triggers (e.g., user messages from Telegram or other channels) overlap with the
communication channel ingress model. We should align the trigger envelope and routing metadata
with the channel/session model defined in docs/product_requirements/communication_channels.md.
All inbound triggers must include channel metadata to preserve reply routing and inbox behavior.

## Approach
- Triggers are sent via messages on the runtime, similar to how agents communicate.
- User-facing triggers are routed to `UserAgent`, which publishes to `System4` (root).
- The VSM can decide which systems should receive which triggers and manage this itself.
- Triggers are provided via external tools; the trigger setup must be flexible and extensible.
- Triggers should be similar to the current OpenClaw implementation.
- Trigger ownership is assigned to root team System3 for all trigger types.
- Trigger routing decisions are handled by a dedicated routing skill.

## Trigger Config
- system that receives the trigger (usually system 1)
- prompt that gets added to the received trigger as context
- tool that provides the trigger
- system that owns the trigger and can manage it (root team System3)
- channel metadata requirements (channel, session_id, channel-specific ids)
- channel access controls (allowlist/blocklist, webhook secret)
- delivery mode (polling vs webhook, if applicable)

## Trigger Envelope (Inbound)
Required fields:
- `channel`
- `session_id`

Channel-specific metadata:
- Telegram text: `telegram_chat_id`, `telegram_message_id`
- Telegram callback: `telegram_chat_id`, `telegram_message_id`, `telegram_callback_id`,
  `telegram_callback_data`
- Telegram voice: `telegram_chat_id`, `telegram_message_id`, `telegram_file_id`
- Telegram reset: `reset_session` set to `"true"`

## Existing Triggers
### User Message
The user already can trigger the system, however this feature is currently hard coded.
Here the user can (via cli) send a trigger to the `UserAgent`, which publishes to root `System4`.

### Telegram Inbound
Telegram delivers inbound user prompts via polling or webhook mode.
Supported inbound types:
- Text messages
- Callback queries (inline keyboard)
- Voice messages (transcribed to text before routing)

All Telegram triggers are recorded in the shared inbox with `channel=telegram` and the
corresponding `session_id`.

## Routing Skill
Trigger routing decisions are handled by a dedicated routing skill. The skill determines the
target system for each trigger.

## Inbox Scope
Only user prompts, system questions, and system responses are recorded in the shared inbox.
Other trigger types do not create inbox entries unless they originate from a user-facing channel.
## Planned Triggers
### Cron
A simple cronjob that can trigger the systems regularly.
See docs/product_requirements/cron_triggers.md.
