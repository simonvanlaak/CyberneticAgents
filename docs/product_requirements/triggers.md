# Triggers
## Goal
The system needs to receive triggers from the environment, for example an email that gets received.

## Approach:
- Triggers are sent via messages on the runtime, similar to how agents communicate.
- The VSM can decide which systems should receive which triggers and manage this itself.
- Triggers are provided via external tools, the trigger setup needs to be flexible and expandible
- Triggers should be have similar as currently implemented in openclaw

## Trigger Config
- system that receives the trigger (usually system 1)
- prompt that gets added to the received trigger as context
- tool that provides the trigger
- system that owns the trigger and can manage it (usually system 3)

## Existing Triggers
### User Message
The user already can trigger the system, however this feature is currently hard coded.
Here the user can (via cli) send a trigger to the root system 4.
## Planned Triggers
### Cron
A simple cronjob that can trigger the systems regularly.
#### Heartbeat
There should be a default cronjob existing that acts as a "heartbeat".
- [ ] Which system type should receive the heartbeat?
- [ ] What sholud be the default action on the heartbeat? is this really necssary or just a waste of tokens?
- [ ] We need one heartbeat for the system4 to ensure viablity. A very good default prompt is required here.
### E-Mail
On receiving an email a message gets triggered.
