# Onboarding Task Routing Bugs

## Responses Disappear When System4 Emits Plain Text
- Symptom: System4 generates a response but it never reaches CLI/Telegram.
- Evidence: `logs/runtime_20260205_223132.log` shows an assistant response with no tool call; `logs/cli_inbox.json` has no `system_response`.
- Cause: Only tool calls are routed; plain assistant text is not delivered.
- Impact: Users see no response during onboarding/interview steps.

## Onboarding SOP Tasks Stay Pending (No Assignee)
- Symptom: Tasks created for the onboarding SOP remain `PENDING` with `assignee: -`.
- Cause: `execute_procedure()` materializes tasks first, then `System3.handle_initiative_assign_message` returns early if tasks already exist:
  - `src/cyberagent/services/procedures.py` → `_materialize_tasks()`
  - `src/agents/system3.py` → `if task_service.has_tasks_for_initiative(...): return`
- Impact: Tasks exist but are never assigned, so no System1 execution occurs.

## Initiative Assignment Fails on Invalid Message Source
- Symptom: Runtime error when System4 assigns an initiative to System3.
- Evidence: `logs/runtime_20260205_223132.log` → `Invalid name: Thesis Scope & Requirements Assessment. Only letters, numbers, '_' and '-' are allowed.`
- Cause: `InitiativeAssignMessage.source` is set to `initiative.name`, which can include spaces and symbols:
  - `src/cyberagent/db/models/initiative.py` → `get_assign_message()`
- Impact: System3 never handles the initiative, so no tasks are created/assigned.
