# Memory Feature

## Overview
The memory system provides scoped CRUD for agent, team, and global memory with optimistic concurrency, conflict tracking, and optional audit/metrics hooks. It is exposed to agents as the `memory_crud` tool and backed by AutoGen memory adapters (in-memory list or ChromaDB).

## Core Capabilities
- **CRUD + promotion**: Create, read, update, delete, list, and promote memory entries across scopes.
- **Scope routing**: Per-scope stores via `StaticScopeRegistry` for `agent`, `team`, and `global`.
- **Optimistic concurrency**: `etag` + `if_match` handling with conflict entry creation.
- **Pagination**: Cursor-based list responses with `next_cursor` and `has_more`.
- **Layering**: Memory entries include a `layer` (`working`, `session`, `long_term`, `meta`).
- **RBAC/VSM enforcement**: Permission checks per scope and system type.

## Data Model
`MemoryEntry` fields include:
- `id`, `scope`, `namespace`, `owner_agent_id`, `content`
- `priority`, `source`, `confidence`
- `layer`, `version`, `etag`
- `tags`, `expires_at`
- `conflict`, `conflict_of`

Conflicts are stored as separate entries with `conflict=True` and `conflict_of` set to the original ID.

## Runtime Behavior
- `SystemBase` registers `MemoryCrudTool` only when the system has the `memory_crud` skill grant.
- `MemoryCrudTool` also enforces skill permissions at runtime (deny-by-default).
- `MemoryCrudTool` uses `MemoryCrudService` for permission checks, scope defaults, pagination, and concurrency.
- Default scope is `agent`.
- Agent scope defaults `namespace` to the actor’s agent ID.
- Team/global scopes require an explicit `namespace`.
- Update/delete with `if_match` mismatch raises `MemoryConflictError` and creates a conflict entry.

## Permission Model Summary
From `check_memory_permission`:
- **Global**: Sys4 only.
- **Team**: Read allowed for any system in the same team. Write requires Sys3+.
- **Agent**: Owner only; also enforces same-team access.

## Backends & Configuration
Supported backends:
- `list`: In-memory AutoGen `ListMemory` per scope.
- `chromadb`: ChromaDB-backed AutoGen memory via `ChromaDBVectorMemory`.

Environment variables:
- `MEMORY_BACKEND` (`list` or `chromadb`)
- `MEMORY_CHROMA_COLLECTION`
- `MEMORY_CHROMA_PATH`
- `MEMORY_CHROMA_HOST`
- `MEMORY_CHROMA_PORT`
- `MEMORY_CHROMA_SSL`

## Observability
`MemoryCrudService` can emit:
- Audit events via `MemoryAuditSink` (e.g., `LoggingMemoryAuditSink`)
- Metrics via `MemoryMetrics` (reads, writes, latency, hit rate)

These hooks are optional and only active when passed in.

## Error Handling (Tool Level)
`memory_crud` returns structured errors:
- `INVALID_PARAMS` for input validation failures
- `FORBIDDEN` for RBAC/VSM denials
- `NOT_FOUND` for missing entries
- `CONFLICT` for `if_match` mismatches
- `NOT_IMPLEMENTED` when the configured backend does not support an operation

## How to Test
- `python3 -m pytest tests/memory/ -v`

## File Map
- Models and interfaces:
  - `src/cyberagent/memory/models.py`
  - `src/cyberagent/memory/store.py`
  - `src/cyberagent/memory/registry.py`
- CRUD + permissions:
  - `src/cyberagent/memory/crud.py`
  - `src/cyberagent/memory/permissions.py`
- Backends + config:
  - `src/cyberagent/memory/backends/autogen.py`
  - `src/cyberagent/memory/backends/chromadb.py`
  - `src/cyberagent/memory/config.py`
- Tool exposure:
  - `src/cyberagent/tools/memory_crud.py`
  - `src/agents/system_base.py`
