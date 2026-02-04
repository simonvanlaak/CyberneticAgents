# Memory Architecture (Technical Notes)

## Purpose
Describe how MemEngine integrates with the system memory architecture without duplicating PRD details. This doc is the technical source of truth for the `memory_crud` API contract and implementation-level defaults.

## Decision
We will use MemEngine for core memory operations (storage, retrieval, summarization, reflection primitives) and wrap it with system-specific layers for scope, permissions, and auditability.

## Integration Overview
1. Memory CRUD is exposed as the `memory_crud` agent skill that gates all memory operations.
2. A scope registry routes requests to the correct memory store based on `agent`, `team`, or `global` scope.
3. MemEngine operates behind the registry as the core memory framework.
4. Permission checks happen before any MemEngine operation.
5. All memory CRUD actions are logged for audit and observability.
6. Memory stores are pluggable backends behind the registry.

## AutoGen Memory Features
1. `Memory` protocol (custom stores implement `add`, `query`, and `update_context`).
2. `autogen_ext.memory.chromadb.ChromaDBVectorMemory` (ChromaDB-backed vector memory).

## Scope Routing
1. Agent scope: private store per agent.
2. Team scope: shared store per team.
3. Global scope: shared store across all teams, writeable only by Sys4 agents.

## Lifecycle
1. Session logs feed session memory.
2. Reflection jobs distill summaries and rules into long-term memory.
3. Compaction summaries are generated when context limits are approached.
4. Prompt-time pruning reduces tool output noise without rewriting stored history.
5. Reflections write to agent scope by default and are promoted to team/global only via explicit promotion.

## Scope Defaults
1. Default write target scope is `agent` unless explicitly specified.

## Conflict Handling
Use optimistic concurrency for updates plus versioned merge for conflicts:
1. Each memory entry includes a `version` (integer) and `etag` (opaque string) that change on update.
2. Update/delete operations accept optional `if_match` to enforce optimistic concurrency.
3. If `if_match` does not match the current `etag`, reject with a conflict error and store the new content as a separate entry with `conflict_of` pointing to the original entry ID and `conflict` flag set.
4. Conflicts require review to reconcile.

## Permissions (Skill-Gated)
See `docs/product_requirements/memory.md` for the authoritative permissions list.

## Bulk Operations
1. Bulk CRUD is allowed.
2. Hard limit of 10 items per request.

## Shared Memory Schema (Team and Global)
See `docs/product_requirements/memory.md` for the authoritative schema. This doc only adds:
1. `layer` (`working` | `session` | `long_term` | `meta`) to make layer explicit for shared entries.
2. `version` (integer) and `etag` (opaque string) for optimistic concurrency.
3. `conflict` (boolean) and `conflict_of` (nullable ID) for conflict tracking.

## Retention and Pruning Defaults
See `docs/product_requirements/memory.md` for the authoritative defaults.

## Memory CRUD API Contract (Phase 0 Resolution)
### Endpoint
`memory_crud` skill with actions: `create`, `read`, `update`, `delete`, `list`, `promote`.

### Request (common fields)
1. `action` (required)
2. `scope` (`agent` | `team` | `global`, optional; default `agent`)
3. `namespace` (required for team/global; optional for agent)
4. `layer` (`working` | `session` | `long_term` | `meta`, optional; defaults by pipeline)
5. `items` (array; for bulk operations; max 10)
6. `filters` (for `list`/`read`)
7. `cursor` (for `list`)
8. `limit` (for `list`, default 25, max 100)
9. `if_match` (optional ETag for `update`/`delete`)

### Response (common fields)
1. `items` (array)
2. `next_cursor` (nullable string)
3. `has_more` (boolean)
4. `errors` (array of {`code`, `message`, `details`})

### Pagination Rules
1. Cursors are opaque tokens; clients must not parse, construct, or persist them across sessions.
2. If `next_cursor` is missing or `null`, pagination ends.
3. Invalid cursors return an invalid-params error.
4. `has_more` mirrors whether additional results are available.

### Error Codes
1. `INVALID_PARAMS` (malformed cursor, invalid scope)
2. `FORBIDDEN` (RBAC/VSM deny)
3. `NOT_FOUND` (missing entry)
4. `CONFLICT` (ETag mismatch or conflict flag set)
5. `RATE_LIMITED` (request throttled)

## Audit Logging Defaults
Audit logs must capture authorization failures and avoid sensitive data; log volume should be balanced to avoid blind spots.

## Backend Choice (Phase 1)
Phase 1 uses ChromaDB via `autogen_ext.memory.chromadb.ChromaDBVectorMemory` with explicit persistence configuration.
