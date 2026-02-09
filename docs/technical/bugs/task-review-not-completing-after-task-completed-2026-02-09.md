# Task Review Not Completing After Task Completed (2026-02-09)

## Summary
Task #1 (`Collect user identity and disambiguation links`) reached `completed` state but was not finalized by System3 review (did not become `approved`).

Status as of 2026-02-09 code review:
- The original unhandled parse-exception path is **partially fixed**.
- The workflow can still leave tasks in `completed` without deterministic review closure metadata/retry policy.

## What Happened
1. System3 assigned Task #1 to System1.
2. System1 completed the task and published `TaskReviewMessage(task_id=1)` to System3.
3. System3 started review flow, found no baseline policies for `System1/root`, and escalated to System5.
4. System5 bootstrapped baseline policies and retriggered `TaskReviewMessage(task_id=1)`.
5. System3 review then failed while parsing structured JSON (`CasesResponse`) from model output.
6. In the original run, handler parsing failed and review did not complete; task stayed `completed`.

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
System3 review handler relies on strict structured JSON parse (`CasesResponse`) and a fallback prompt. If fallback is also non-JSON, review cannot produce policy cases for the task.

Relevant code path:
- `src/agents/system3.py` -> `handle_task_review_message`
  - First structured parse can fail.
  - Fallback run is attempted.
  - Fallback parse can also fail.
  - Current code catches outer exceptions and routes an `InternalErrorMessage` to System5.

Current verified behavior in code/tests:
- `src/agents/system3.py` catches review exceptions and routes internal error to policy system (`_route_internal_error_to_policy_system`).
- `tests/agents/test_system3.py::test_system3_task_review_routes_internal_error_to_system5_on_parse_failure` verifies no uncaught failure path and `InternalErrorMessage` publication.

## Impact
- Task remains `completed` but unreviewed/unapproved.
- Initiative progression can stall or become inconsistent.
- Repeated retriggers may accumulate noisy context and repeated failures.

## Revised Gap
Even though unhandled exceptions are now avoided, the failure outcome is still under-specified:
- No explicit failure marker is persisted to the task when parse fails (`set_task_case_judgement` is not called in failure branch).
- No bounded retry policy exists in System3 review flow.
- Failure escalation currently uses `InternalErrorMessage`; the policy/review workflow may need a domain-level signal (`PolicySuggestionMessage` or equivalent structured review-failure event) for deterministic recovery.

## Updated Fix Plan
Treat LLM output parse failures as explicit workflow outcomes with deterministic persistence and retry behavior.

1. Keep current exception safety behavior
   - Preserve current outer exception handling (already implemented).
   - Keep hard exceptions only for true invariants (missing task/assignee/policy system).

2. Add deterministic failure persistence
   - On primary+fallback parse failure, persist a structured failure record on the task (for example in `case_judgement` payload) with:
     - `phase` (`primary` or `fallback`)
     - `reason`
     - `timestamp`
     - `retry_count`
   - Ensure this branch never calls `approve_task`.

3. Use a domain-level recovery signal to System5
   - Prefer publishing `PolicySuggestionMessage(policy_id=None, task_id=...)` with explicit review-parse-failure context, or introduce a dedicated review-failure message type.
   - Keep `InternalErrorMessage` for true internal faults; do not rely on it as the only normal recovery path for predictable parse failures.

4. Add bounded retry semantics
   - Prevent infinite review retrigger loops.
   - Track retry count in persisted review failure metadata.
   - Stop automatic retries after a small max (e.g., 2-3), then require explicit policy/manual intervention.

5. Improve observability
   - Emit explicit logs containing `task_id`, assignee, phase (`primary`/`fallback`), and retry count.
   - Include whether escalation used internal-error or domain-level recovery event.

## TDD Regression Test Cases (Required)
1. Keep existing parse-failure safety test (already present)
   - `tests/agents/test_system3.py::test_system3_task_review_routes_internal_error_to_system5_on_parse_failure`
   - Confirms no uncaught exception path and no approval on parse failure.

2. Add failing test: parse failure persists deterministic marker
   - Arrange: primary JSON-generation failure + fallback non-JSON.
   - Assert: `set_task_case_judgement` stores failure metadata payload.
   - Assert: `approve_task` not called.

3. Add failing test: bounded retry behavior
   - Arrange: repeated parse failures for same task.
   - Assert: retries capped and escalation behavior switches to explicit manual/policy intervention after limit.

4. Keep happy fallback test
   - Primary structured attempt fails, fallback returns valid JSON.
   - Assert normal review continuation and judgement persistence.

## Fast Re-Check Commands
```bash
cyberagent status
cyberagent logs --level ERROR --limit 200
rg -n "TaskReviewMessage|PolicySuggestionMessage|Failed to parse response|MessageHandlerException|task_id\":1" logs/runtime_*.log -S
```
