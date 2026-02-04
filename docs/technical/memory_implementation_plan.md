# Memory Implementation Plan

## Phase 0: Preflight
- [x] Confirm `memory_crud` skill API contract (request/response schema, error codes, pagination).
- [x] Confirm default scope behavior (agent scope) and explicit promotion rules.
- [x] Confirm backend choice for Phase 1 (ChromaDB, SQLite, filesystem, or hybrid).

## Phase 1: Core Interfaces
- [x] Define memory domain models (entry, scope, metadata, conflicts).
- [x] Define store interface (add, query, update, delete, list).
- [x] Define scope registry interface (agent/team/global routing).
- [x] Define audit logging interface and event schema.

## Phase 2: Skill Layer
- [x] Implement `memory_crud` skill handler entry points (create/read/update/delete/list).
- [x] Enforce RBAC + VSM permission checks before any operation.
- [x] Enforce scope defaults (agent) when scope is omitted.
- [x] Implement cursor-based pagination for list operations.

## Phase 3: Backends
- [x] Implement AutoGen `Memory` protocol adapter.
- [x] Implement ChromaDB-backed store adapter behind the registry.
- [x] Add pluggable backend configuration (env/config file).

## Phase 4: Reflection + Promotion
- [x] Write reflection outputs to agent scope by default.
- [x] Implement explicit promotion command/path to team/global scopes.
- [x] Implement conflict detection + versioned merge handling.

## Phase 5: Observability + Safety
- [x] Log CRUD events (who/what/when/where + scope) with redaction rules.
- [x] Track retrieval hit rate, injection size, and latency.
- [x] Add privacy safeguards for delete + redaction.

## Phase 6: Tests (TDD)
- [ ] Unit tests for store interface contracts.
- [ ] Unit tests for scope routing and default scope behavior.
- [ ] Unit tests for RBAC + VSM permission gating.
- [ ] Unit tests for pagination, conflict handling, and promotion rules.
- [ ] Unit tests for optimistic concurrency (`if_match`/ETag) and conflict entry creation.
- [ ] Integration tests for Chroma-backed store (if enabled).

## API Contract Test Plan (Memory CRUD)
1. Cursor pagination returns `next_cursor` and `has_more`; `next_cursor` is `null` when `has_more` is false.
2. Invalid cursor returns `INVALID_PARAMS` with no partial results.
3. `limit` enforces default (25) and max (100); requests above max clamp or error per contract.
4. Scope default is `agent` when omitted; explicit `scope` overrides.
5. `namespace` is required for `team`/`global` and optional for `agent`.
6. Bulk operations reject more than 10 items with `INVALID_PARAMS`.
7. `if_match` mismatch on update/delete yields `CONFLICT` and creates a conflict entry with `conflict_of` set.
8. RBAC/VSM violations return `FORBIDDEN` and produce an audit log entry.

## Phase 7: CLI + Docs
- [ ] Expose `memory_crud` via CLI (if applicable).
- [ ] Update PRD/tech docs with final API schema and config.
