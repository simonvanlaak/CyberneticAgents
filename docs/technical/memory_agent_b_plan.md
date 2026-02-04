# Memory Implementation Plan - Agent B (Scope Routing + RBAC/VSM)

## Scope
Own scope registry routing, default scope behavior, and permission gating.

## Files (expected)
1. `src/cyberagent/services/` for scope registry and routing
2. `src/rbac/` (legacy path) for RBAC integration
3. `tests/` for unit tests

## Deliverables
1. Scope registry with `agent`, `team`, `global` routing. ✅
2. Default scope behavior (`agent` when omitted). ✅
3. RBAC + VSM permission checks with clear errors. ✅

## TDD Tasks
1. Write failing tests for scope routing and default scope. ✅
2. Write failing tests for RBAC/VSM gating (allowed/denied per Sys level). ✅
3. Implement minimal code to pass tests. ✅
4. Refactor for clarity and type completeness. ✅

## Acceptance Criteria
1. Permissions match PRD rules for Sys1-Sys5 across `team` and `global`. ✅
2. `namespace` requirement enforced for `team`/`global`. ✅
3. No CRUD handler or pagination logic in this agent's code. ✅

## Status
Complete.
