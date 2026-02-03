# Memory Implementation Plan

## Phase 0: Preflight
- [ ] Confirm `memory_crud` skill API contract (request/response schema, error codes, pagination).
- [ ] Confirm default scope behavior (agent scope) and explicit promotion rules.
- [ ] Confirm backend choice for Phase 1 (ChromaDB, SQLite, filesystem, or hybrid).

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
- [ ] Log CRUD events (who/what/when/where + scope) with redaction rules.
- [ ] Track retrieval hit rate, injection size, and latency.
- [ ] Add privacy safeguards for delete + redaction.

## Phase 6: Tests (TDD)
- [ ] Unit tests for store interface contracts.
- [ ] Unit tests for scope routing and default scope behavior.
- [ ] Unit tests for RBAC + VSM permission gating.
- [ ] Unit tests for pagination, conflict handling, and promotion rules.
- [ ] Integration tests for Chroma-backed store (if enabled).

## Phase 7: CLI + Docs
- [ ] Expose `memory_crud` via CLI (if applicable).
- [ ] Update PRD/tech docs with final API schema and config.
