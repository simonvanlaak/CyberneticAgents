# Streamlit Read-Only Kanban UI Plan (Phase 1)

## Goals
- Deliver a very fast local UI for viewing task flow only.
- Show tasks in Kanban columns by status with assignee visibility.
- Keep existing SQLite/service layer as single source of truth.
- Avoid any write/edit capability in phase 1.

## Scope
- In scope:
  - Local Streamlit app.
  - Read-only Kanban view for task statuses:
    - `pending`, `in_progress`, `completed`, `approved`, `rejected`
  - Filters: team, strategy, initiative, assignee.
  - Auto-refresh option (e.g., every 5-10 seconds).
- Out of scope:
  - Task edits (status, assignee, content).
  - Authentication and multi-user access control.
  - Replacing existing CLI/runtime orchestration.

## Current Data Model (Verified)
- Team: `src/cyberagent/db/models/team.py`
- Purpose: `src/cyberagent/db/models/purpose.py`
- Strategy: `src/cyberagent/db/models/strategy.py`
- Initiative: `src/cyberagent/db/models/initiative.py`
- Task: `src/cyberagent/db/models/task.py`
- Status enum: `src/enums.py`
- Existing hierarchy/status query reference: `src/cyberagent/cli/status.py`

## Architecture Overview
- Add one Streamlit app under `src/cyberagent/ui/kanban.py`.
- App reads data via existing DB connection/query logic (prefer reusing `status` aggregation patterns).
- No new API service required for phase 1.
- Run command:
  - `streamlit run src/cyberagent/ui/kanban.py`

## UI Layout
- Top bar filters:
  - Team selector
  - Strategy selector
  - Initiative selector
  - Assignee selector
  - Auto-refresh toggle + interval selector
- Main board:
  - 5 columns matching status enum values
  - Task cards show:
    - task id
    - task name
    - assignee
    - initiative name/id
  - Optional card count per column
- Secondary view:
  - Table fallback below board for search/sort/export-copy workflows

## Delivery Plan

### Milestone 1: Foundation (Day 1-2)
1. Add `streamlit` dependency to `pyproject.toml`.
2. Create app scaffold and local run instructions.
3. Implement DB read path and status-grouped data model.
4. Add basic board rendering.

### Milestone 2: Filters + refresh (Day 2-3)
1. Add filter controls (team/strategy/initiative/assignee).
2. Add auto-refresh and manual refresh button.
3. Add empty-state and error-state handling.

### Milestone 3: Polish + docs (Day 3-4)
1. Improve card layout readability.
2. Add table fallback section.
3. Add docs in `docs/features/` once implementation is complete.

## TDD Plan
1. RED: Test data query helper returns expected grouping by status.
2. RED: Test filters restrict result set correctly.
3. GREEN: Implement minimal query and mapping code to pass tests.
4. REFACTOR: Isolate query/mapping helpers into testable functions.
5. Add smoke test for app module import + basic render entrypoint.

## Security and Access
- Phase 1:
  - Local-only use.
  - No write endpoints.
  - No external exposure by default.
- Phase 2 (if needed):
  - Reverse proxy auth.
  - RBAC-aware filtered visibility by team/user.

## Risks
- Streamlit auto-refresh can create unnecessary DB polling load if interval is too low.
- Without auth, app must remain local-only.
- Large task volumes may require pagination/virtualization tuning.

## Success Criteria
1. Users can open a local page and see tasks grouped by status.
2. Assignee is visible on each task card.
3. Filters work for team/strategy/initiative/assignee.
4. UI remains read-only and does not alter task state.

## Effort Estimate
- MVP (read-only Kanban): ~1-3 days
- Hardened local UI (performance tuning + docs + tests): ~3-5 days
