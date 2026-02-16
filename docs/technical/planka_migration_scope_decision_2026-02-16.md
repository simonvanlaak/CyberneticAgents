# Planka migration scope + decision (Taiga -> Planka)

Ticket: #130  
GitHub Project item: #130

## Decision summary

CyberneticAgents will migrate operator-facing task execution from Taiga to Planka.

### What we replace

- **Taiga UI** for day-to-day operator task tracking.
- **Taiga adapter/worker** runtime integration paths used for task polling and status transitions.

### What we keep

- **GitHub `stage:*` labels** as the implementation workflow source of truth.
- Existing issue-driven build/ship process (stage transitions, comments, and verification flow).

## Scope boundaries

| Area | In scope now | Out of scope now |
|---|---|---|
| Runtime task board | Planka-based board + worker loop integration | Rebuilding GitHub workflow in Planka |
| Migration | Taiga -> Planka cutover for active runtime queues | Full historical Taiga data migration |
| Automation | Stage-aware execution loop from Planka cards/lists | New product planning process changes |

## Required Planka primitive mapping

| Planka primitive | Maps from Taiga | Purpose in CyberneticAgents |
|---|---|---|
| Project | Taiga Project | Workspace boundary for a deploy/environment (e.g., production automation) |
| Board | Taiga board/workflow view | Main operational board used by automation + operators |
| List | Taiga task status column | Canonical task state lane consumed by worker loop |
| Card | Taiga task | Executable unit with title, details, assignee, and comments |

## Status mapping (GitHub stages <-> Planka lists)

GitHub remains authoritative for implementation work; Planka lists mirror the same stage semantics for runtime visibility.

| GitHub stage label | Planka list name | Meaning |
|---|---|---|
| stage:backlog | backlog | Parked, not active |
| stage:queued | queued | Awaiting automation triage |
| stage:needs-clarification | needs-clarification | Missing required answers |
| stage:ready-to-implement | ready-to-implement | Authorized for implementation |
| stage:in-progress | in-progress | Work actively being executed |
| stage:in-review | in-review | Implemented, awaiting verification |
| stage:blocked | blocked | Cannot proceed without external input |

## Migration phases

### Phase 1 — Scope + contracts

1. Freeze Taiga contract as legacy and document Planka contract (project/board/list/card + list names).
2. Define environment variables and credentials for Planka runtime worker.
3. Add/update docs that describe stage semantics and ownership.

### Phase 2 — Runtime migration

1. Implement Planka worker loop that reads cards from mapped lists.
2. Keep transitions deterministic (single writer: automation sets list transitions, humans comment/clarify).
3. Validate with dry-runs on a non-critical board and confirm list/state transitions.

### Phase 3 — Operator cutover

1. Switch operational runbook and daily usage from Taiga UI to Planka board.
2. Stop Taiga worker execution paths in production.
3. Keep GitHub stage labels unchanged; verify end-to-end flow (queued -> in-review).
4. Archive Taiga-specific runtime docs after acceptance.

## Cutover plan

- **Cutover trigger:** Planka worker loop passes quality gate and one full task cycle in staging.
- **Execution window:** low-traffic maintenance window.
- **Steps:**
  1. Pause automation loop.
  2. Ensure no task remains mid-transition in Taiga.
  3. Enable Planka worker + board mappings.
  4. Run one canary task from `queued` to `in-review`.
  5. Resume normal automation.
- **Success criteria:** no status drift between GitHub stage labels and Planka list states for canary + next 3 tasks.

## Risks and mitigations

- **Risk:** state drift between GitHub labels and Planka lists.  
  **Mitigation:** enforce explicit mapping table and transition guards in worker logic.
- **Risk:** hidden Taiga-only assumptions in scripts/docs.  
  **Mitigation:** follow-up docs refactor ticket to remove Taiga-first commands.
- **Risk:** operator confusion during tool switch.  
  **Mitigation:** cutover checklist + concise operator runbook updates.
