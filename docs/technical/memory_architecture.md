# Memory Architecture (Technical Notes)

## Purpose
Describe how MemEngine integrates with the system memory architecture without duplicating PRD details.

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
Use versioned merge. Conflicts are stored as separate entries with a conflict flag and require review to reconcile.

## Permissions (Skill-Gated)
1. Permissions are enforced by existing skill permission rules before any operation.
2. Sys3-Sys5 can write to team scope.
3. Sys1-Sys2 can read team scope but cannot edit it.
4. No system can edit another team's knowledge.
5. Only Sys4 (any team) can read and write global scope.

## Bulk Operations
1. Bulk CRUD is allowed.
2. Hard limit of 10 items per request.

## Shared Memory Schema (Team and Global)
1. `id`
2. `scope` (`agent` | `team` | `global`)
3. `namespace`
4. `owner_agent_id`
5. `content`
6. `tags` (optional)
7. `priority` (`low` | `medium` | `high`)
8. `created_at`
9. `updated_at`
10. `expires_at` (nullable)
11. `source` (`reflection` | `manual` | `tool` | `import`)
12. `confidence` (0.0 to 1.0)

## Retention and Pruning Defaults
1. Use compaction-style summaries for durable retention when context limits are approached.
2. Use transient pruning at prompt time to reduce tool output noise without rewriting stored history.

## Best-Practice Defaults (External Guidance)
1. `memory_crud` list endpoints use cursor-based pagination; return `next_cursor` (or next link) and `has_more`, set a reasonable default page size, and enforce a maximum page size to protect performance.
2. Treat cursors as opaque values and do not decode, modify, or construct them manually.
3. Audit logs should include who/what/when/where for each event, capture authorization failures, and avoid logging secrets, tokens, or sensitive personal data; restrict and monitor access to logs.
4. If using ChromaDB in phase 1, configure persistence explicitly: local usage via `PersistentClient(path=...)` (defaults to `.chroma` if no path is provided) and server usage via `chroma run --path ...` (default persist dir is `./chroma`, server defaults to `localhost:8000`).
