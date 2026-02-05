# Message Routing PRD

## Summary
Define a unified message routing system that can route inbound communications
from multiple channels (Telegram, email, CLI, etc.) to the correct team and
system/agent. Routing rules must be editable by agents (via System3 policies),
preserve original message content (forwarding, not re-sending), and provide a
dead-letter queue for messages without a valid receiver.

## Goals
- Route inbound messages to the correct team and system based on configurable
  rules, without special-casing onboarding or any single SOP.
- Support multiple channels with channel-specific filters (e.g., sender email,
  Telegram user id).
- Allow System3 to modify routing rules at runtime.
- Preserve original message content and metadata to avoid information loss.
- Provide a dead-letter queue with clear fallback handling.

## Non-Goals
- Implement a full CRM or email parsing system.
- Define every future channel integration (only the routing layer).
- Replace existing SOP logic; this should complement SOP execution.

## Problem Statement
Inbound user messages currently default to System4. This makes SOP-driven
interviews (onboarding) brittle and causes follow-up questions to be generated
out of context. A general routing system is needed to reliably deliver messages
to the appropriate System1 handler for active initiatives and future channels.

## User Stories
- As a user, when I respond to an onboarding interview, my reply should reach
  the interviewing agent without being reinterpreted by another system.
- As an operator, I can define routing rules so certain email senders go to
  specific teams or systems.
- As System3, I can adjust routing rules based on active initiatives.
- As a developer, I can inspect messages that could not be routed.

## Requirements
### Functional
- The system must route inbound messages to a team and recipient system/agent
  based on configurable routing rules.
- Routing rules must support channel-specific filters (e.g., Telegram chat/user
  ids, CLI session id).
- Routing must not depend on an active initiative; rules should persist beyond
  initiative lifecycles and remain active until changed.
- Routing rules must be editable by agents (System3) at runtime.
- Messages must be forwarded (original content + metadata preserved).
- If no route matches, messages go to a dead-letter queue with a defined handler.
- Routing must follow the recursion hierarchy: messages enter at root team and
  can only be routed down to a team’s System1s or subteams.
- Rule matching is exact-match only in v1 (no regex/prefix/wildcards in filters).

### Non-Functional
- Routing must be deterministic and auditable.
- Routing must be low-latency (< 200ms per message in normal conditions).
- Routing decisions must be logged with the rule applied (or DLQ reason).

## Data Model (Draft)
### Routing Skill (Draft)
- A new agent skill that exposes tools to create/update/disable routing rules
  and to inspect the dead-letter queue.
- System3 uses this skill to manage routing at runtime.

### RoutingRule
- `id`
- `team_id`
- `name`
- `channel` (e.g., `telegram`, `email`, `cli`)
- `filters` (JSON):
  - `telegram_chat_id`
  - `telegram_user_id`
  - `telegram_chat_type` (private/group/supergroup/channel)
  - `session_id` (for cli or channel sessions)
  - `channel` (redundant but explicit)
- `priority` (higher wins)
- `targets` (one or more recipients):
  - `{ "system_id": "System4/root" }`
  - `{ "team_id": "onboarding" }`
  - Targets may include multiple entries; a single rule can fan-out to both
    teams and systems.
- `active` (bool)
- `created_by_system_id`
- `updated_by_system_id`

### DeadLetterMessage
- `id`
- `channel`
- `payload` (original message + metadata)
- `reason`
- `received_at`
- `handled_by_system_id` (optional)
- `status` (pending/handled)

## Routing Flow (Draft)
1. Inbound message arrives (channel adapter).
2. Root team receives the message and builds a routing context (channel, sender metadata).
3. Query routing rules ordered by priority and match filters.
4. If matched, forward the original message to the target System1 or subteam.
5. If the target is a subteam, repeat steps 2-4 within that subteam.
6. If no rule matches in a team, enqueue to that team’s dead-letter queue and
   notify that team’s System4.

## Example Flow (Draft)
1. A Telegram voice reply arrives from `chat_id=5488423581`.
2. Root team checks its routing rules:
   - Rule A: `channel=telegram`, `telegram_user_id=5488423581` -> subteam `onboarding`.
3. Message is forwarded (original content + metadata) to subteam `onboarding`.
4. Subteam `onboarding` checks its rules:
   - Rule B: `channel=telegram`, `telegram_chat_id=5488423581` -> System1 `onboarding_interviewer`.
5. Message is delivered to System1 `onboarding_interviewer`.
6. If Rule B did not exist, the message would enter the onboarding team DLQ,
   and onboarding System4 would be notified to resolve it.

## SOP Integration (Draft)
- SOPs may define routing requirements (e.g., required roles or target agents).
- When an SOP is loaded, System3 uses the routing skill to register or update
  the required routing rules for the team.

## Open Questions
1. None for v1.

## Success Metrics
- 95%+ of inbound messages routed without DLQ in normal operation.
- Onboarding interview follow-ups are delivered to the interviewer agent 100%
  of the time.
- Routing changes by System3 take effect within seconds.
## Team Config Schema (Draft)
Teams may define initial routing rules in their defaults (e.g.,
`config/defaults/teams/root_team.json`). v1 schema:

```json
{
  "routing_rules": [
    {
      "name": "Default DLQ",
      "channel": "*",
      "filters": {},
      "priority": 0,
      "active": true,
      "targets": [
        { "system_id": "System4/root" }
      ]
    }
  ]
}
```

Defaults:
- `active` defaults to `true` if omitted.
- `priority` defaults to `0` if omitted.
- `filters` defaults to `{}` if omitted.
