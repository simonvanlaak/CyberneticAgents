# Memory Implementation Plan - Agent C (Skill Layer + Pagination + Conflicts)

## Scope
Own `memory_crud` skill handlers, cursor pagination, and conflict handling with optimistic concurrency.

## Files (expected)
1. `src/cyberagent/tools/` or `src/cyberagent/cli/` for skill handlers
2. `tests/` for unit tests

## Deliverables
1. `memory_crud` handlers: `create`, `read`, `update`, `delete`, `list`, `promote`.
2. Cursor pagination with `next_cursor` and `has_more`.
3. `if_match` handling and conflict entry creation on mismatch.

## TDD Tasks
1. Write failing tests for pagination contract and invalid cursor errors.
2. Write failing tests for `if_match` conflict behavior.
3. Write failing tests for bulk limit (max 10 items).
4. Implement minimal code to pass tests.
5. Refactor for clarity and type completeness.

## Acceptance Criteria
1. Pagination defaults: `limit=25`, max `limit=100`.
2. Invalid cursor returns `INVALID_PARAMS` without partial results.
3. `if_match` mismatch yields `CONFLICT` and creates entry with `conflict_of`.
4. No changes to store interfaces or RBAC logic beyond calling them.
