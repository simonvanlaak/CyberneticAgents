# Onboarding Runtime Errors (2026-02-08)

Source snapshot:
- Command: `cyberagent status`
- Command: `cyberagent logs`
- Runtime log file: `logs/runtime_20260208_223835.log`

## 1) System1 Task Execution Fails Due to Invalid Message Source Name
- Symptom:
  - Tasks get assigned and marked in progress, but System1 fails while processing `TaskAssignMessage`.
  - Status shows:
    - `Task 1 [IN_PROGRESS] (assignee: System1/root)`
    - `Task 7 [IN_PROGRESS] (assignee: System1/root)`
    - remaining tasks stay pending.
- Evidence:
  - `logs/runtime_20260208_223835.log`:
    - `ERROR [autogen_core] Error processing publish message for System1/root`
    - `ValueError: Invalid name: System3/root. Only letters, numbers, '_' and '-' are allowed.`
- Current impact:
  - Assignment happens, but operational execution by System1 crashes.
  - Onboarding appears to advance in status while actual task work is blocked.
- Likely cause:
  - `TaskAssignMessage.source` is emitted as `System3/root` (contains `/`), and downstream OpenAI message transformation rejects it.

## 2) System4 Fails With Required Tool-Choice 400 Errors
- Symptom:
  - Suggestion handling and user-message processing intermittently fail with 400 from Groq/OpenAI endpoint.
- Evidence:
  - `logs/runtime_20260208_223835.log`:
    - `ERROR [autogen_core] Error processing publish message for System4/root`
    - `openai.BadRequestError: Error code: 400 ... 'Tool choice is required, but model did not call a tool'`
    - Failed generation text: `Awaiting your reply about the specific topic or research question for your bachelor thesis.`
  - `ERROR [src.cyberagent.cli.headless] Failed to deliver suggestion ...` repeated for one queued suggestion file.
- Current impact:
  - Runtime retries and suggestion delivery fail noisily.
  - User interaction can stall when model returns plain text instead of a tool call under `tool_choice="required"` mode.
- Likely cause:
  - `System4.handle_user_message` enforces tool-choice-required execution path, but prompt/model output sometimes returns plain text.

## 3) Telegram Pairing Warning (Non-blocking)
- Symptom:
  - Warning appears during runtime startup/operation.
- Evidence:
  - `WARNING [src.cyberagent.channels.telegram.pairing] Failed to store Telegram admin chat ids in 1Password.`
- Current impact:
  - No direct evidence this blocks onboarding flow.
  - Likely affects persistence of admin chat-id metadata only.

## What Is Working Despite Errors
- System4 strategy generation succeeded and created strategy/initiatives.
- Initiative assignment source sanitization appears active for initiatives:
  - Log shows `InitiativeAssignMessage` source as `initiative_2`.
- System3 can assign first tasks for initiatives (assignment tool calls succeed).

## Priority Order
1. Fix invalid source name on `TaskAssignMessage` path (`System3/root` -> safe token format).
2. Add fallback handling for System4 tool-required flow when model emits plain text.
3. Investigate 1Password warning separately (lower priority).
