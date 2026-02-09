# Onboarding Memory and False Task Completion Bug

## Summary
Task `#1` (`Collect user identity and disambiguation links`) was marked `completed` even though the result text clearly asks for missing input. This indicates two separate issues:

1. Onboarding context was not available to `System1` where needed.
2. `System1` marks tasks `completed` unconditionally after generating any reply.

## What I verified

### 1) Onboarding memory write path exists
- `src/cyberagent/cli/onboarding_memory.py`:
  - `store_onboarding_memory(...)`
  - `store_onboarding_memory_entry(...)`
- These currently write with:
  - `scope=global`
  - `namespace=user`

### 2) Global memory read permissions are now open to all systems
- `src/cyberagent/memory/permissions.py`:
  - Global scope `READ` is allowed for all system types, including `SystemType.OPERATION`.
- `src/agents/system_base.py`:
  - Memory retrieval resolves `AGENT`, `TEAM`, and `GLOBAL` scopes.
- `tests/memory/test_permissions.py`:
  - Explicitly verifies global reads for `SystemType.OPERATION`.

This part of the original bug is considered fixed.

### 3) Why task still gets marked completed incorrectly
- `src/agents/system1.py` in `handle_assign_task_message(...)`:
  - Calls `task_service.complete_task(task, result)` after any model response.
- There is no completion-quality gate before status flips to `COMPLETED`.

This is why a clarification request can still become a completed task result.

## Current status

- `Onboarding memory accessibility`: fixed.
- `False completion from System1`: not fixed.

## Agreed implementation plan

### A) Add a structured execution contract for System1
- Introduce a typed response model for task execution output:
  - `status: done | needs_input | blocked`
  - `result: str`
  - `follow_up_question: str | None` (required when `needs_input`)
  - `blocking_reason: str | None` (required when `blocked`)
- Parse this as structured output from `System1` instead of relying on free-form text.

### B) Replace unconditional completion in System1
- In `System1.handle_assign_task_message(...)`:
  - `done` -> call `task_service.complete_task(...)`
  - `needs_input` -> do **not** complete; keep task active and escalate question upstream
  - `blocked` -> do **not** complete; escalate blocker/capability gap upstream

### C) Add explicit task-state transitions in task service
- Extend `src/cyberagent/services/tasks.py` with non-completion transitions (for example):
  - `mark_task_needs_input(task, question)`
  - `mark_task_blocked(task, reason)`
- Keep state transition logic centralized in task service.

### D) Add a defensive gate in System3 review
- In `System3.handle_task_review_message(...)`, avoid approval/progression when the execution status is `needs_input` or `blocked`.
- Route follow-up to user/System5 as appropriate.

### E) Follow strict TDD for this fix
- Write failing tests first, then implement:
  - `tests/agents/test_system1.py`: verify `needs_input`/`blocked` never call `complete_task(...)`
  - `tests/services/test_task_service.py`: verify new transitions and persisted state
  - `tests/agents/test_system3.py`: verify non-`done` outcomes are not approved/progressed

## Expected outcome after fix
- Onboarding/user context is actually retrievable by operational agents.
- Tasks are not marked complete unless output satisfies task objective.
- Dashboard status and results better reflect real execution quality.
