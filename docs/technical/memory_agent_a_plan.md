# Memory Implementation Plan - Agent A (Core Domain + Store Interfaces)

## Scope
Own core domain models and store interface contracts, with unit tests.

## Files (expected)
1. `src/cyberagent/domain/` (or nearest domain module)
2. `src/cyberagent/services/` for store abstractions if needed
3. `tests/` for unit tests

## Deliverables
1. Domain models for memory entries, metadata, and conflict fields.
2. Store interface with `add`, `query`, `update`, `delete`, `list`.
3. Unit tests for interface contracts (including required fields).

## TDD Tasks
1. Write failing tests for model validation and serialization.
2. Write failing tests for store interface behavior and invariants.
3. Implement minimal code to pass tests.
4. Refactor for clarity and type completeness.

## Acceptance Criteria
1. All new functions include complete type hints.
2. Tests cover schema fields: `layer`, `version`, `etag`, `conflict`, `conflict_of`.
3. Tests for `list` include default ordering and stable pagination expectations.
4. No RBAC or scope routing logic in this agent's code.
