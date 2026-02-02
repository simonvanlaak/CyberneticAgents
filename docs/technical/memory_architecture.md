# Memory Architecture (Technical Notes)

## Purpose
Describe how MemEngine integrates with the system memory architecture without duplicating PRD details.

## Decision
We will use MemEngine for core memory operations (storage, retrieval, summarization, reflection primitives) and wrap it with system-specific layers for scope, permissions, and auditability.

## Integration Overview
1. Memory CRUD is exposed as an agent skill that gates all memory operations.
2. A scope registry routes requests to the correct memory store based on `agent`, `team`, or `global` scope.
3. MemEngine operates behind the registry as the core memory framework.
4. Permission checks happen before any MemEngine operation.
5. All memory CRUD actions are logged for audit and observability.

## Scope Routing
1. Agent scope: private store per agent.
2. Team scope: shared store per team.
3. Global scope: shared store across all teams, writeable only by Sys4 agents.

## Lifecycle
1. Session logs feed session memory.
2. Reflection jobs distill summaries and rules into long-term memory.
3. Compaction summaries are generated when context limits are approached.
4. Prompt-time pruning reduces tool output noise without rewriting stored history.

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
