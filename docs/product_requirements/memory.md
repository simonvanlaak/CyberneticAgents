# Memory PRD

## Purpose
Define a first-class memory system for agents that is reliable, scalable, and cost-aware while improving task continuity, personalization, and cross-agent coordination.

## Scope
This PRD covers memory for single-agent and multi-agent workflows in the core runtime and CLI use cases.

## Goals
1. Improve task continuity across sessions without dumping full logs into the prompt.
2. Reduce hallucination by selective recall and context pruning.
3. Provide explainable, auditable, and editable memory artifacts.
4. Enable cross-agent memory sharing for coordinated workflows.
5. Control latency and token cost via prioritization and compression.
6. Expose memory CRUD as an agent skill for safe, auditable operations.

## Non-Goals
1. A fully generalized enterprise knowledge graph for all teams and all time.
2. Replacing existing AutoGen memory features. We will integrate and extend, not duplicate.
3. Cross-workspace federation in phase 1.

## Best Practices (2025-early 2026)

### 1) Treat Memory and Context as a First-Class Design Concern
Memory is not a passive log. It is an active system that decides when to write, select, compress, and isolate information. This is often called context engineering.

### 2) Layered Memory Architecture
Separate memory into distinct layers to avoid context overload:
1. Working memory. Immediate conversation window.
2. Session memory. Task-scoped persistence for the current session.
3. Long-term memory. Durable facts, preferences, and learned patterns.
4. Meta memory. Distilled rules or heuristics learned from reflections.

### 3) Hybrid Retrieval and Indexing
Combine multiple retrieval strategies to improve recall:
1. Semantic retrieval with vector similarity.
2. Keyword or sparse indexing for exact matches.
3. Compression or summarization to fit retrieved content into limited context.

### 4) Reflection and Synthesis Over Raw Logs
Prefer distilled facts, patterns, and rules rather than full transcripts. Periodic reflection reduces noise and creates actionable memory.

### 5) Memory Should Evolve, Not Just Accumulate
Memory should update and prune. It should capture user preferences and generalized patterns while avoiding endless append-only growth.

### 6) Minimize Context Overload
Avoid "context rot" by pruning irrelevant or outdated entries and by using summaries instead of full logs.

### 7) Cross-Agent Memory and Coordination
Share key decisions, preferences, and constraints across agents via shared memory hubs or routing. This reduces repetition and improves consistency.

### 8) Prioritization and Cost Control
Rank memories by relevance and recency. Use dynamic compression to keep prompts compact and reduce token costs.

### 9) Explainable and Auditable Memory
Store memory in interpretable formats that developers can inspect, edit, and delete. Avoid opaque embedding dumps as the only memory store.

## Requirements

### Functional
1. Provide a layered memory API with explicit read and write paths per layer.
2. Support hybrid retrieval: semantic plus keyword lookup.
3. Implement memory compression before prompt injection.
4. Provide reflection jobs that synthesize session logs into distilled facts or rules.
5. Support memory pruning and updates with clear policies.
6. Enable cross-agent memory sharing with access control.
7. Provide audit and edit capability for stored memories.
8. Implement memory CRUD as an agent skill with explicit permission checks.
9. Ensure the skill supports scoped operations per layer and per namespace.
10. Default retention and pruning should mirror OpenClaw: compaction-style summaries for durable retention and transient pruning for prompt size control.
11. Permissions must follow existing skill permission rules with VSM constraints:
    1. Sys3-Sys5 can write to team scope.
    2. Sys1-Sys2 can read team scope but cannot edit it.
    3. No system can edit another team's knowledge.
    4. Only Sys4 (any team) can read and write global scope.
12. Bulk memory CRUD is allowed with a hard limit of 10 items per request.
13. Shared memory entries must include a `layer` field to make the layer explicit for team/global data.

### Non-Functional
1. Keep latency acceptable for CLI usage.
2. Ensure memory injection respects token budgets.
3. Support privacy constraints and explicit delete operations.

## Architecture (Phase 1)
1. Memory store abstraction with pluggable backends.
2. Per-agent memory registry with explicit scope boundaries.
3. Shared memory hub for team or global coordination.
4. Retrieval pipeline: search, rank, compress, inject.
5. Reflection pipeline: summarize, extract rules, update memory.
6. Agent skill: `memory_crud` for create, read, update, delete with audit logs.
7. Shared memory schema with minimal, auditable fields for team and global scopes.
8. Permission gate that enforces skill-level RBAC and VSM scope rules before any CRUD action.

## Data Flow
1. Session logs feed into session memory.
2. Periodic reflection extracts durable facts and rules.
3. Long-term memory is updated with distilled facts.
4. Retrieval and compression select the minimal context needed per task.
5. When approaching context limits, compact older session history into summaries while keeping recent messages intact.
6. Prune tool results transiently at prompt time without rewriting on-disk history.

## Minimal Shared Memory Schema (Team and Global)
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
13. `layer` (`working` | `session` | `long_term` | `meta`)
14. `version` (integer)
15. `etag` (opaque string)
16. `conflict` (boolean)
17. `conflict_of` (nullable ID)

## Observability
1. Log memory reads and writes with identifiers and timestamps.
2. Track memory hit rate, injection size, and retrieval latency.
3. Expose summaries of new WARNING or ERROR lines via CLI.
4. Log memory CRUD skill invocations with caller agent ID and scope.

## Privacy and Safety
1. Store only necessary data. Avoid sensitive information in long-term stores.
2. Provide explicit delete operations for user data.
3. Keep memory formats human-auditable.

## Open Questions
None. Phase 0 preflight decisions are captured in the Decisions section.

## Decisions
1. Conflict handling: use versioned merge. Keep both entries, mark conflict, and require review to reconcile.
2. Use MemEngine as the memory framework for core memory operations, integrated with our scopes, RBAC, and CRUD skill.
3. Default retention and pruning: use compaction-style summaries for durable retention when context limits are approached; use transient pruning at prompt time to reduce tool output noise without rewriting stored history.
4. Permissions model: Sys3-Sys5 can write to team scope; Sys1-Sys2 can read team scope but cannot edit it; no system can edit another team's knowledge; only Sys4 (any team) can read and write global scope.
5. Minimal cross-agent schema: use the shared memory schema fields defined in this PRD for team and global scopes.
6. Bulk operations: allowed with a hard limit of 10 items per request.
7. AutoGen memory features: wrap the AutoGen `Memory` protocol and `autogen_ext.memory.chromadb.ChromaDBVectorMemory` behind scope routing, RBAC, audit logging, and the `memory_crud` skill.
8. Scope defaults: reflections write to agent scope by default and are promoted to team/global only via explicit promotion; default write target scope is `agent` unless specified.
9. Phase 0 API contract and pagination rules are defined in `docs/technical/memory_architecture.md`.
10. Phase 1 backend choice: ChromaDB (via `autogen_ext.memory.chromadb.ChromaDBVectorMemory`) with explicit persistence configuration.
11. Layer vs scope: layers describe time/horizon (working/session/long_term/meta) while scopes describe visibility (agent/team/global); they are orthogonal.

## Technical Notes
See `docs/technical/memory_architecture.md`.

## References
1. https://docs.openclaw.ai/concepts/memory
2. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
3. https://mem0.ai/blog/context-engineering-ai-agents-guide
4. https://rlancemartin.github.io/2025/12/01/claude_diary/
5. https://weaviate.io/blog/context-engineering
6. https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot/
7. https://arxiv.org/abs/2512.12686
8. https://arxiv.org/abs/2601.03785
