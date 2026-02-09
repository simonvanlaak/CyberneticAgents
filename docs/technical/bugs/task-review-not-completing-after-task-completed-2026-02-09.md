# Task Review Not Completing After Task Completed (2026-02-09)

## Summary
Task #1 (`Collect user identity and disambiguation links`) reached `completed` state but was not finalized by System3 review (did not become `approved`).

## What Happened
1. System3 assigned Task #1 to System1.
2. System1 completed the task and published `TaskReviewMessage(task_id=1)` to System3.
3. System3 started review flow, found no baseline policies for `System1/root`, and escalated to System5.
4. System5 bootstrapped baseline policies and retriggered `TaskReviewMessage(task_id=1)`.
5. System3 review then failed while parsing structured JSON (`CasesResponse`) from model output.
6. Handler raised an exception, so review did not complete and task stayed `completed`.

## Evidence (Runtime Logs)
- File: `logs/runtime_20260209_005323.log`
- Task completion + review publish:
  - `03:33:21.078` `System1/root -> TaskReviewMessage -> System3/root` for `task_id=1`
- No-policy bootstrap path:
  - `03:33:21.081` System3 publishes `PolicySuggestionMessage` (no policies)
  - `03:33:21.141` System5 publishes retriggered `TaskReviewMessage` for `task_id=1`
- Review failure:
  - `03:33:22.299` `Error processing publish message for System3/root`
  - Exception: `ValueError: Failed to parse response ... Invalid JSON ...` (expected `CasesResponse`)

## Root Cause
System3 review handler relies on strict structured JSON parse (`CasesResponse`) and has a fallback prompt, but still hard-fails when fallback output is non-JSON prose.

Relevant code path:
- `src/agents/system3.py` -> `handle_task_review_message`
  - First structured parse can fail.
  - Fallback run is attempted.
  - Fallback parse also fails and raises.
  - Exception aborts review processing.

## Impact
- Task remains `completed` but unreviewed/unapproved.
- Initiative progression can stall or become inconsistent.
- Repeated retriggers may accumulate noisy context and repeated failures.

## Recommended Fix Direction
1. Make `handle_task_review_message` resilient when both strict and fallback parse fail:
   - Catch fallback parse failure and route to deterministic safe behavior instead of throwing.
2. Safe behavior options:
   - Emit `PolicySuggestionMessage` indicating review parse failure and request policy/review re-run, or
   - Persist an explicit `case_judgement` failure marker and requeue `task_review` via queue with bounded retries.
3. Add regression tests for:
   - Non-JSON primary + non-JSON fallback outputs in review flow.
   - Ensure no unhandled exception and deterministic post-failure state.

## Best-Practice Fix Plan (Agreed)
Treat LLM output parsing errors as recoverable workflow outcomes, not handler-fatal exceptions.

1. Keep hard exceptions only for true invariants
   - Continue raising for missing task/assignee/policy system.
   - Do not raise out of `handle_task_review_message` for model output parse failures.

2. Guard fallback parse as well as primary parse
   - Current fallback parse (`_get_structured_message` on fallback response) can still throw.
   - Wrap fallback parse in its own `try/except`.
   - On fallback parse failure, execute deterministic failure handling and `return`.

3. Deterministic failure handling behavior
   - Persist a structured failure marker via `task_service.set_task_case_judgement(...)` (for example: phase, reason, retry_count, timestamp).
   - Publish `PolicySuggestionMessage(policy_id=None, task_id=...)` to System5 requesting policy/review intervention.
   - Do not call `approve_task` in this branch.

4. Add bounded retry semantics
   - Prevent infinite review retrigger loops.
   - Track retry count in stored review metadata and stop automatic retries after a small max (e.g., 2-3).
   - After max retries, require explicit policy/manual intervention.

5. Improve observability
   - Emit explicit error logs containing `task_id`, assignee, phase (`primary` or `fallback`), and retry count.
   - This supports fast diagnosis via `cyberagent logs --level ERROR`.

## TDD Regression Test Cases (Required)
1. Failing test first: primary + fallback both non-JSON
   - Arrange: first review call raises JSON-generation failure; fallback returns prose/non-JSON text.
   - Assert: no uncaught exception from handler.
   - Assert: `PolicySuggestionMessage` published to System5.
   - Assert: `approve_task` not called.
   - Assert: failure marker persisted through `set_task_case_judgement`.

2. Keep and pass existing happy fallback test
   - Primary JSON generation fails.
   - Fallback returns valid JSON.
   - Assert normal review continuation and approval behavior.

## Fast Re-Check Commands
```bash
cyberagent status
cyberagent logs --level ERROR --limit 200
rg -n "TaskReviewMessage|PolicySuggestionMessage|Failed to parse response|MessageHandlerException|task_id\":1" logs/runtime_*.log -S
```
