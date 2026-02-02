# Product Requirements – Communication Channels

## Summary
CyberneticAgents should feel reachable wherever the user already communicates. We need a coherent product experience across channels (CLI first, Telegram next, later email/Slack/web), with a shared **Inbox** so messages are never “lost” and users can continue a conversation from any channel.

This document defines the product goals, user experience, and a high‑level roadmap for multi‑channel communication. Technical implementation details are intentionally light at this stage.

## Problem
Today the user only interacts via CLI. That’s limiting for:
1. Timely responses when the CLI isn’t open.
2. Natural workflows (many users live in messaging apps).
3. Continuity: messages can feel disconnected without a shared thread.

## Goals
1. **Reachability**: Users can receive and send messages via CLI and Telegram (MVP).
2. **Continuity**: A single Inbox shows all messages regardless of channel.
3. **Clarity**: Users always know where a message came from and where replies go.
4. **Trust**: Sensitive content is handled carefully and channels are explicit.

## Non‑Goals (for now)
1. Full Slack/Email/WhatsApp support (later).
2. Rich UI clients (mobile/desktop app).
3. Multi‑user collaboration and shared inboxes.

## Users & Jobs
### Primary User
An individual building with CyberneticAgents who wants rapid feedback while away from the CLI.

### Core Jobs‑to‑Be‑Done
1. “Let me receive important questions without keeping the CLI open.”
2. “Let me respond from my phone and have the system continue the thread.”
3. “Let me review prior questions and answers in one place.”

## Experience Principles
1. **Single Inbox**: All messages flow through one mental model.
2. **Channel Transparency**: Every message shows its source channel.
3. **Low Friction**: Minimal setup once; onboarding should guide the user.
4. **Graceful Degradation**: If a channel is offline, the user still sees the message.

## MVP Scope (CLI + Telegram)
### CLI
- Inbox shows new questions and answers.
- A reply in CLI continues the conversation.

### Telegram
- Incoming Telegram messages appear in the Inbox.
- The system can respond back in Telegram.
- Telegram messages are clearly labeled as “Telegram” in the Inbox.

## Shared Inbox (Product Definition)
The Inbox is a single feed that aggregates:
1. **User prompts** (from any channel)
2. **System questions** (from any system)
3. **System responses** (delivered back to the originating channel)

Each entry should include:
1. Channel (CLI, Telegram)
2. Timestamp
3. Sender (User, System4, etc.)
4. Conversation/thread identifier

## Setup & Onboarding
1. Onboarding should detect which channels are configured.
2. Users should be prompted to connect Telegram with clear steps.
3. If a channel isn’t available, the system should explain why and how to fix it.

## Risks & Open Questions
1. **Channel Identity**: How to map a Telegram user to the CLI user?
2. **Threading Model**: One global thread or per‑channel thread?
3. **Notification Strategy**: When should we push vs wait?
4. **Privacy**: Which messages can safely be mirrored across channels?

## Roadmap
1. **Phase 1**: CLI + Telegram, shared Inbox, minimal setup.
2. **Phase 2**: Email or Slack, more advanced notification preferences.
3. **Phase 3**: Multi‑user teams and shared inboxes.

## Success Metrics
1. % of users who connect at least one external channel.
2. Response time to system questions (before vs after Telegram).
3. Reduced “missed question” events (no pending questions >24h).

## OpenClaw‑Aligned Requirements (Routing & Sessions)
The communication experience should match OpenClaw’s routing model:
1. **Deterministic routing**: Replies must return to the same channel that received the message. The model does not choose the channel.
2. **Channel + session keys**: Messages are grouped by a session key derived from agent + channel + conversation scope.
3. **Direct messages**: By default, direct chats collapse into a single “main” session for continuity.
4. **Group/room isolation**: Groups and channels remain isolated per channel + group/channel id.
5. **Thread isolation**:
   - Slack/Discord threads append a thread id to the base session.
   - Telegram forum topics embed a topic id in the group session key.
6. **Multi‑account awareness**: Account identity is part of the routing context when the user has multiple accounts.
7. **Configurable DM scoping**: Direct message scoping should support:
   - `main` (all DMs share the main session),
   - `per-peer` (DMs isolated by sender),
   - `per-channel-peer` (channel + sender),
   - `per-account-channel-peer` (account + channel + sender).
8. **Identity linking (optional)**: The same person can map to a single identity across channels for unified DM sessions.

## Technical Sources (for later implementation)
- AutoGen Core Message & Communication (RoutedAgent, message handlers, publish/subscribe topics):
  - https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/framework/message-and-communication.html
- AutoGen Core API reference (publish_message, TopicId, message_id):
  - https://microsoft.github.io/autogen/stable/reference/python/autogen_core.html
- OpenClaw Channel Routing (deterministic routing, session keys, thread/group handling):
  - https://docs.openclaw.ai/concepts/channel-routing
- OpenClaw Session Management (DM scoping, identity links):
  - https://docs.openclaw.ai/concepts/session
