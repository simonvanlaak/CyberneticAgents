# Cron Triggers
## Goal
Define cron-based triggers that can invoke systems on a schedule, including a default heartbeat.

## Scope
- Cron scheduling mechanism and configuration.
- Trigger envelope and routing metadata alignment with communication channels.
- Default heartbeat trigger.

## Dependencies
Depends on docs/product_requirements/communication_channels.md
See docs/product_requirements/triggers.md

## Approach
- Cron triggers are emitted into the runtime as standard trigger messages.
- Each cron trigger specifies the target system, schedule, and optional context prompt.
- Channel metadata should be included when the trigger is user-facing or creates inbox entries.

## Trigger Config
- system that receives the trigger (usually system 1)
- schedule (cron expression or fixed interval)
- prompt/context to include with the trigger
- system that owns the trigger and can manage it (usually system 3)
- delivery mode (local scheduler or external cron source)

## Heartbeat Trigger
There should be a default cronjob that acts as a heartbeat.

### Open Questions
- Which system type should receive the heartbeat?
- What should be the default action on the heartbeat? Is it necessary or just a waste of tokens?
- We need one heartbeat for System4 to ensure viability. A strong default prompt is required.

## Planned Triggers
- Team health check (System3)
- Viability scan (System4)
