# Skill Permissions Big Picture Architecture Plan

## Status
- Owner: Platform / Security / Runtime
- Date: 2026-02-02
- Scope: End-to-end architecture for team envelope + system grant skill permissions

## Why This Exists
- Skills are becoming the primary capability surface for agent systems.
- We need strict least-privilege controls without slowing down agent evolution.
- Permission checks must be deterministic, auditable, and easy to reason about.

## Current Baseline (Verified in Code)
- Generic Casbin RBAC is active in `src/rbac/enforcer.py` and `src/rbac/model.conf`.
- Team and system service files exist but are thin delegates:
  - `src/cyberagent/services/teams.py`
  - `src/cyberagent/services/systems.py`
- `System5` exists as policy actor but lacks permission CRUD implementation in `src/agents/system5.py`.
- Default team bootstrapping exists in `src/cyberagent/core/state.py` (`default_team` plus default systems).

## Target Architecture (Big Picture)

### 1) Two-Layer Permission Model
- Layer A: Team envelope (what a team is allowed to grant).
- Layer B: System grants (what a specific system can execute).
- Effective execution permission = `team envelope` AND `system grant`.

### 1.1) VSM Recursion Permission Inheritance
- System5 may recurse a System1 into a sub-team.
- The sub-team presents as the original System1 to the parent/root team.
- The sub-team inherits all permissions from the originating System1.
- Permission changes to the originating System1 must propagate to the sub-team and all recursive descendants.

### 2) Root Team Governance
- Root team is the first default team created at startup.
- Root team has one System1..System5 set and can grant globally.
- Root team bypasses team-envelope restrictions for supported skills.

### 3) Dedicated Skill-Permissions Casbin Model
- Keep current RBAC model for existing tool flows.
- Add separate model file for skill permissions: `src/rbac/skill_permissions_model.conf`.
- Use explicit service/runtime composition instead of complex matcher logic.

### 4) Service-First Authority Boundary
- `System5` calls service APIs only (no direct Casbin writes).
- `teams.py` owns envelope CRUD and cascade revoke.
- `systems.py` owns grant CRUD, max-5 enforcement, and execute checks.
- Recursion linkage is handled in services/runtime, not by direct Casbin writes.

### 5) Runtime Enforcement Gate
- Before any skill execution:
  1. Resolve `team_id`, `system_id`, `skill_name`.
  2. Evaluate team envelope.
  3. Evaluate system grant.
  4. Return allow/deny with normalized deny category.
- Deny category precedence: `team_envelope` > `system_grant`.
- For recursed sub-teams, also evaluate origin System1 grant in the parent team.

## Canonical Data Conventions
- Envelope subject: `team:{team_id}`
- System subject: `system:{system_id}`
- Skill resource: `skill:{skill_name}`
- Action: `allow`

These keep policy rows readable, queryable, and migration-safe.

### Recursion Linkage (New)
- Store a stable mapping of `sub_team_id -> origin_system_id + parent_team_id`.
- Runtime/services must use this mapping to enforce inherited grants.

#### Proposed Persistence (Concrete)
- New table: `data/recursions` (SQLite via SQLAlchemy)
  - `sub_team_id` INTEGER PRIMARY KEY
  - `origin_system_id` INTEGER NOT NULL
  - `parent_team_id` INTEGER NOT NULL
  - `created_at` TEXT NOT NULL
  - `created_by` TEXT NOT NULL
  - Indexes:
    - `idx_recursions_origin_system_id` on `origin_system_id`
    - `idx_recursions_parent_team_id` on `parent_team_id`
- Invariants:
  - Each `sub_team_id` maps to exactly one origin System1.
  - `origin_system_id` must belong to `parent_team_id`.
  - Recursion is read-only after creation (no reassignment).

## Core Components and Responsibilities

### Runtime and Execution
- `src/cyberagent/tools/cli_executor/openclaw_tool.py`
  - Integrate skill permission gate before skill invocation.
  - Return deterministic error envelope on deny.

### Permission Services
- `src/cyberagent/services/teams.py`
  - `list_allowed_skills`
  - `add_allowed_skill`
  - `remove_allowed_skill` (must cascade revoke grants in same team)
  - `set_allowed_skills`

- `src/cyberagent/services/systems.py`
  - `list_granted_skills`
  - `add_skill_grant` (must enforce envelope + max 5)
  - `remove_skill_grant`
  - `set_skill_grants` (reject > 5)
  - `can_execute_skill`

### Policy Actor
- `src/agents/system5.py`
  - Invoke only service methods for permission CRUD.
  - Reject out-of-scope actions (cross-team, envelope violation, cap violation).

### Casbin Integration
- New enforcer path for skill permissions (parallel to existing enforcer).
- Casbin remains source of truth; backing storage can be Casbin adapter tables or policy rows per implementation choice.

## Lifecycle Flows

### A) Grant Skill to System
1. System5 requests grant via `systems.add_skill_grant`.
2. Service resolves system -> team.
3. Service checks envelope contains skill.
4. Service checks current grants count < 5.
5. Service writes Casbin grant policy and logs audit event.

### B) Revoke Skill from Team Envelope
1. System5 requests revoke via `teams.remove_allowed_skill`.
2. Service removes envelope entry.
3. Service revokes matching system grants in that team (cascade).
4. Service returns count of revoked grants and logs audit event.

### C) Execute Skill
1. Runtime asks `systems.can_execute_skill`.
2. Service runs envelope check then system-grant check.
3. Runtime proceeds on allow, denies on failure with structured category.
4. If `system_id` belongs to a recursed sub-team, service also checks origin System1 grant in the parent team.

## Error and Observability Contract
- Deny payload must include:
  - `team_id`
  - `system_id`
  - `skill_name`
  - `failed_rule_category`
- Grant-time failures may return `system_skill_limit`.
- Execution failures use `team_envelope` or `system_grant`.
- Emit structured audit events for all CRUD and execution decisions:
  - actor, target, change, timestamp, outcome, reason category.

## Security Model
- Default deny; no implicit grants.
- No wildcard grants except explicit root-admin behavior.
- Secrets and permission systems are orthogonal:
  - Permission allow does not bypass required secret checks.
 - Recursion does not create new permission sources; it reuses origin System1 grants.

## Rollout Plan

### Phase 1 - Foundations
- Add dedicated skill permission model and enforcer wrapper.
- Add service-layer APIs (no System5 wiring yet).

### Phase 2 - Enforcement
- Wire runtime execution gate into CLI skill execution path.
- Add deterministic deny payloads and structured events.

### Phase 3 - Governance
- Implement System5 permission CRUD handlers using services.
- Enforce team scope and mutation constraints.

### Phase 4 - Hardening
- Add integration tests for full flow.
- Add migration/backfill scripts if existing permissions need normalization.

## Phased Implementation Plan (TDD-Enforced)

### Phase 1: Model + Services Foundations
- RED: add failing tests for team envelope CRUD, system grant CRUD, max-5 enforcement, and deny precedence.
- GREEN: implement skill-permissions Casbin model + enforcer wrapper; add service APIs in `teams.py` and `systems.py`.
- REFACTOR: normalize error payloads and add minimal structured audit logs.

### Phase 2: Runtime Enforcement
- RED: add failing tests for execution gating and structured deny payloads.
- GREEN: integrate `can_execute_skill` into CLI skill execution.
- REFACTOR: align deny category precedence (`team_envelope` then `system_grant`).

### Phase 3: Governance via System5
- RED: add failing tests for System5 CRUD flows and team-scope constraints.
- GREEN: implement System5 permission operations using services only.
- REFACTOR: lock down cross-team mutation checks and logging.

### Phase 4: Recursion Support
- RED: add failing tests for recursion linkage and inherited grants.
- GREEN: persist recursion linkage and enforce origin System1 grants for recursed sub-teams.
- REFACTOR: optimize lookup paths and keep policy writes minimal.

### Phase 5: Hardening and Integration
- RED: add failing integration tests for root team bypass, cascade revoke, and deep recursion.
- GREEN: improve data integrity checks and add migration/backfill notes.
- REFACTOR: finalize observability coverage and ensure performance stays acceptable.

## Implementation Checklist

### Foundation
- [ ] Add `src/rbac/skill_permissions_model.conf`.
- [ ] Add dedicated skill-permissions enforcer module in `src/rbac/`.
- [ ] Define subject/resource/action naming helpers (`team:*`, `system:*`, `skill:*`, `allow`).

### Services
- [ ] Extend `src/cyberagent/services/teams.py` with envelope CRUD APIs.
- [ ] Extend `src/cyberagent/services/systems.py` with grant CRUD APIs.
- [ ] Implement grant-time max-5 enforcement in system grant services.
- [ ] Implement envelope revoke cascade to remove matching system grants in-team.
- [ ] Implement `can_execute_skill` with deny precedence (`team_envelope` then `system_grant`).

### Runtime Enforcement
- [ ] Integrate permission gate in CLI skill execution path.
- [ ] Return structured deny payload with `team_id`, `system_id`, `skill_name`, `failed_rule_category`.
- [ ] Emit structured allow/deny events with traceable decision context.

### System5 Integration
- [ ] Add/extend System5 permission CRUD handlers in `src/agents/system5.py`.
- [ ] Ensure System5 uses services only (no direct Casbin writes).
- [ ] Enforce team-scope boundaries for System5 operations.

### Testing (TDD)
- [ ] Add unit tests for team envelope service behavior.
- [ ] Add unit tests for system grant service behavior.
- [ ] Add unit tests for max-5 grant-time rule.
- [ ] Add unit tests for deny precedence behavior.
- [ ] Add integration tests for System5 grant/revoke and runtime execute checks.

### Observability and Audit
- [ ] Add structured audit logs for envelope/grant CRUD events.
- [ ] Add structured audit logs for execution permission decisions.
- [ ] Verify actor identity and timestamp are included in all mutation logs.

## TDD-First Test Strategy
- Unit tests:
  - team envelope CRUD
  - system grant CRUD
  - max-5 at grant time
  - deny precedence
  - cascade revoke behavior
- Integration tests:
  - System5-driven grant/revoke
  - runtime execute allow/deny paths
  - root team global behavior

## Open Decisions to Resolve During Implementation
- Exact root-team identity constant (name vs id convention) for bypass checks.
- Whether to keep skill permissions in existing `rbac.db` tables or separate adapter storage.
- Event sink for audit logs (logger only vs persisted audit table).
- Where to persist recursion linkage (table vs policy metadata).

## Success Criteria
- No system executes non-granted skills.
- No team grants skills outside envelope.
- Root team global behavior works deterministically.
- Recursed sub-team permissions always match the originating System1.
- All permission changes and decisions are auditable.
