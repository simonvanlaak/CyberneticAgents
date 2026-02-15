# Task Flow Implementation Audit (Issue #111)

Date: 2026-02-15

## Verdict

**Task flow spec is _not yet fully implemented_.**

Core lifecycle transitions and most review mechanics are implemented and tested, but there are still concrete gaps (especially rejected-task replacement orchestration and one blocked-flow semantic mismatch).

---

## 1) Spec-to-code mapping

### A. Lifecycle state machine
Spec:
- `pending -> in_progress | canceled`
- `in_progress -> completed | blocked`
- `blocked -> in_progress | canceled`
- `completed -> approved | rejected`
- `rejected -> canceled`
- `approved/canceled` terminal

Code:
- `src/cyberagent/services/tasks.py:33-41` (`ALLOWED_TASK_TRANSITIONS`)
- transition enforcement: `src/cyberagent/services/tasks.py:310-324`

Tests:
- `tests/services/test_task_service.py:286-294`
- `tests/services/test_task_service.py:297-352`

Status: **Implemented**

---

### B. System1 execution contract
Spec highlights:
- assignment starts execution (`in_progress`)
- execution result yields `completed` or `blocked`

Code:
- start execution on assignment: `src/agents/system1.py:127`
- blocked path: `src/agents/system1.py:163-175`
- completed path: `src/agents/system1.py:177-186`
- execution failure => blocked: `src/agents/system1.py:187-200`

Status: **Implemented**

---

### C. Review contract eligibility (`completed` + `blocked`)
Code:
- eligibility set: `src/cyberagent/services/tasks.py:43`
- predicate: `src/cyberagent/services/tasks.py:182-189`
- System3 gate: `src/agents/system3.py:735-737`

Tests:
- `tests/services/test_task_service.py:435-460`

Status: **Implemented**

---

### D. Invalid review status handling (+ retry cap)
Spec:
- route `InternalErrorMessage` to System5
- reset task to pending + clear assignee while under cap
- stop auto-retry after cap; wait for System5 remediation

Code:
- counter/reset/cap logic: `src/cyberagent/services/tasks.py:192-238`
- System3 escalation + contract next_action: `src/agents/system3.py:210-253`
- System3 auto-retry assign when allowed: `src/agents/system3.py:255-262`
- System5 now honors `wait_for_policy_remediation`: `src/agents/system5.py:363-376`

Tests:
- service-level retry behavior: `tests/services/test_task_service.py:385-432`
- System3 behavior around cap: `tests/agents/test_system3.py:393-536`
- **new** System5 cap-respect test: `tests/agents/test_system5_validation.py:410-461`

Status: **Implemented** (including this audit’s fix in System5)

---

### E. Completed-path policy outcomes
Spec:
- all Satisfied => `approved`
- any Vague => stay `completed`
- no Vague + any Violated => `rejected`

Code:
- review case accumulation: `src/agents/system3.py:860-912`
- finalize logic: `src/cyberagent/services/tasks.py:214-236`

Tests:
- `tests/services/test_task_service.py:463-549`
- vague routing test exists in System3 suite (`test_system3_routes_vague_review_to_system5...`)

Status: **Implemented**

---

### F. Blocked-path resolution loop
Spec:
- System3 resolves blocked via research/modify/restart
- if not equipped => remediation request to System5
- outcome: resumed execution (pending -> reassigned) or canceled

Code:
- blocked resolution orchestration: `src/agents/system3.py:264-303`
- remediation request to policy system: `src/agents/system3.py:966-997`
- cancel path: `src/agents/system3.py:999-1013`
- modify/restart path: `src/agents/system3.py:1015-1045`

Tests:
- blocked handling coverage: `tests/agents/test_system3.py:289-392`, `tests/agents/test_system3.py:1043-1130`

Status: **Partially implemented**

Reason: restart path currently uses `start_task()` (`blocked -> in_progress`) and can republish to the same assignee; it does not explicitly enforce `pending -> reassign best System1` semantics described in the spec.

---

### G. Rejected flow + replacement attempt creation
Spec:
- `rejected` attempt archived as `canceled`
- replacement task created (same initiative), starts `pending`, no assignee inherited
- System3 reselects best System1

Code reality:
- rejection can be set in finalize review (`src/cyberagent/services/tasks.py:228-231`)
- policy violation handling in System5 currently acknowledges/reasons but does **not** perform archival + replacement orchestration (`src/agents/system5.py:100-188`)

Status: **Missing**

---

### H. Task attempt lineage fields
Spec note says list field (`follow_up_task_ids`) but issue context notes migration to single follow-up field.

Code/DB:
- model fields are single-link: `follow_up_task_id` + `replaces_task_id` (`src/cyberagent/db/models/task.py:46-57`)
- migration helpers for both columns: `src/cyberagent/db/init_db.py:198-233`

Tests:
- lineage rendering/roundtrip in kanban data: `tests/cyberagent/test_kanban_data.py:272-306`

Status: **Implemented in code as single-link lineage**

Doc mismatch: planned spec text still says `follow_up_task_ids` list.

---

## 2) Gap list (enumerated)

1. **Rejected replacement orchestration missing**
   - No implemented path that automatically archives rejected task to `canceled` and creates replacement task with lineage wiring.

2. **Blocked restart semantic mismatch**
   - Current restart path resumes directly toward `in_progress` with existing assignee; spec expects explicit `pending -> reassigned` semantics.

3. **Spec text mismatch on lineage field shape**
   - Planned doc still references `follow_up_task_ids` list, while implementation is single `follow_up_task_id`.

---

## 3) Remaining implementation checklist (Done / Not Done)

- [x] Canonical lifecycle transition map and transition enforcement
- [x] Review-eligible statuses (`completed`, `blocked`)
- [x] Invalid-review retry cap behavior across System3 + System5
- [ ] Rejected -> canceled archival + replacement task creation flow (same initiative)
- [ ] Enforce blocked-resolution resume semantics as `pending -> reassigned` (or explicitly update spec if direct restart is intentional)
- [ ] Update `docs/features/planned/task_flow.md` lineage section to single-link model (`follow_up_task_id`)

---

## 4) Tests updated in this audit

- Added: `test_system5_internal_error_wait_for_remediation_does_not_auto_retry`
  - File: `tests/agents/test_system5_validation.py:410-461`
  - Covers the previously uncovered branch where System5 must not trigger another review when invalid-review auto-retry cap is exhausted.

---

## 5) Clear acceptance statement

**Task flow spec is not yet fully implemented.**

The implementation is close on lifecycle + review control flow, but still needs rejected-replacement orchestration and blocked-resume semantic alignment (or a spec adjustment) before this can be marked complete.
