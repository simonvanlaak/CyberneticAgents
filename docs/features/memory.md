# Memory Feature

## Overview
The memory system provides scoped CRUD for agent, team, and global memory with optimistic concurrency, conflict tracking, and audit/metrics hooks. It is exposed to agents as the `memory_crud` tool and backed by a SQLite record store by default, with optional ChromaDB vector retrieval.

## Core Capabilities
- **CRUD + promotion**: Create, read, update, delete, list, and promote memory entries across scopes.
- **Scope routing**: Per-scope stores via `StaticScopeRegistry` for `agent`, `team`, and `global`.
- **Optimistic concurrency**: `etag` + `if_match` handling with conflict entry creation.
- **Pagination**: Cursor-based list responses with `next_cursor` and `has_more`.
- **Layering**: Memory entries include a `layer` (`working`, `session`, `long_term`, `meta`). Team/global writes must set `layer` explicitly.
- **RBAC/VSM enforcement**: Permission checks per scope and system type.
- **Retrieval + injection**: Prompt-time retrieval with budgeted memory injection and audit logging of retrieved IDs.
- **Reflection**: Summaries can be generated from session logs and stored as memory entries.
- **Pruning**: Expired or low-priority entries can be pruned with a defined policy.
- **MemEngine**: Retrieval/reflection use the MemEngine adapter for consistency.
- **Session log ingestion**: User/assistant turns are recorded into session memory, compacted, and pruned per namespace limits.

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
- Team/global scopes require an explicit `namespace` and `layer`.
- Update/delete with `if_match` mismatch raises `MemoryConflictError` and creates a conflict entry.

## Permission Model Summary
From `check_memory_permission`:
- **Global**: Sys4 only.
- **Team**: Read allowed for any system in the same team. Write requires Sys3+.
- **Agent**: Owner only; also enforces same-team access.

## Backends & Configuration
Supported backends:
- `list`: In-memory AutoGen `ListMemory` per scope.
- `chromadb`: SQLite record store (persistent) with optional ChromaDB vector index integration.

Environment variables:
- `MEMORY_BACKEND` (`list` or `chromadb`)
- `MEMORY_CHROMA_COLLECTION`
- `MEMORY_CHROMA_PATH`
- `MEMORY_CHROMA_HOST`
- `MEMORY_CHROMA_PORT`
- `MEMORY_CHROMA_SSL`
- `MEMORY_SQLITE_PATH`
- `MEMORY_VECTOR_BACKEND`
- `MEMORY_VECTOR_COLLECTION`
- `MEMORY_INJECTION_MAX_CHARS`
- `MEMORY_INJECTION_PER_ENTRY_MAX_CHARS`
- `MEMORY_RETRIEVAL_LIMIT`
- `MEMORY_TEAM_NAMESPACE`
- `MEMORY_GLOBAL_NAMESPACE`
- `MEMORY_SESSION_LOGGING`
- `MEMORY_SESSION_LOG_MAX_CHARS`
- `MEMORY_COMPACTION_THRESHOLD_CHARS`
- `MEMORY_REFLECTION_INTERVAL_SECONDS`
- `MEMORY_MAX_ENTRIES_PER_NAMESPACE`
- `MEMORY_METRICS_LOG`
- `MEMORY_METRICS_LOG_INTERVAL_SECONDS`

## Observability
`MemoryCrudService` can emit:
- Audit events via `MemoryAuditSink` (e.g., `LoggingMemoryAuditSink`)
- Metrics via `MemoryMetrics` (reads, writes, latency, hit rate)

Retrieval logs emit `memory_retrieval` audit events per entry ID. The `memory_crud` tool logs `memory_crud_invocation` with caller agent ID and scope.

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
  - `src/cyberagent/memory/pruning.py`
- Backends + config:
  - `src/cyberagent/memory/backends/autogen.py`
  - `src/cyberagent/memory/backends/chromadb_vector.py`
  - `src/cyberagent/memory/backends/sqlite.py`
  - `src/cyberagent/memory/backends/hybrid.py`
  - `src/cyberagent/memory/backends/vector_index.py`
  - `src/cyberagent/memory/config.py`
- Retrieval + reflection:
  - `src/cyberagent/memory/retrieval.py`
  - `src/cyberagent/memory/reflection.py`
- Session ingestion:
  - `src/cyberagent/memory/session.py`
- Tool exposure:
  - `src/cyberagent/tools/memory_crud.py`
  - `src/agents/system_base.py`
