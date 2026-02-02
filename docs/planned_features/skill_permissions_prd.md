# Skill Permissions PRD

## Document Status
- Status: Draft (implementation-ready)
- Owner: Platform/Security
- Last updated: 2026-02-02

## Purpose
Define the permission model and enforcement requirements for agent skills, including team-level envelopes, system-level grants, and System5 governance flows.

## Recursion Requirement (VSM)
- System5 may trigger recursion by converting a System1 into a sub-team.
- To the root team, the sub-team continues to behave as the original System1 for all interactions.
- The sub-team must inherit all permissions of the originating System1.
- Any permission changes applied by the root team to that System1 must propagate to the sub-team.
- This behavior must support indefinite recursive nesting (System1 -> sub-team -> sub-team ...).

## Policy Backend
- Casbin is the single source of truth for skill permission enforcement.
- Permission checks must happen before every skill execution.

## Core Entities
- Team: organizational boundary for policy scope.
- System instance: executable agent identity inside a team.
- Skill: named capability mapped to a CLI tool contract.
- Actor: principal requesting permission CRUD (primarily System5 and root admins).

## Permission Model

### Team-Level Envelope
- Each team has an allowed-skill set.
- This set defines the maximum skills that can be assigned to systems in that team.
- Team envelope does not auto-enable skills on systems.

### System-Level Grants
- Each system instance has explicit skill grants.
- A system may execute only granted skills.
- A system grant is valid only if the skill is also allowed by the team envelope.
- Hard cap: maximum 5 granted skills per system instance.
- Recursed sub-teams inherit grants from their origin System1 in the parent team.

### Root Team Rule
- Root team has full access to all skills and can grant globally.

## Administrative Actions

### Allowed CRUD Operations
- Team envelope: create/add/remove/list skill allowances.
- System grants: create/add/remove/list skill permissions.
- Read permission decision trace for auditing.

### System5 Authority
- `src/agents/system5.py` is the policy authority actor inside each team.
- System5 can CRUD system grants for systems in its team.
- System5 can only assign skills that exist in that team's envelope.
- System5 actions must be blocked if they exceed team envelope or system cap.
- When a System1 is recursed into a sub-team, root System5 changes to that System1 must apply to the sub-team.

## Enforcement Flow
1. Agent requests skill execution.
2. Runtime resolves team id + system id.
3. Casbin check verifies system grant for the skill.
4. Casbin check verifies team envelope allows that skill.
5. Execution proceeds only if all checks pass.
6. System skill-count limit (<= 5) is enforced at grant mutation time, not execution time.
7. If the system is a recursed sub-team, runtime must also respect the origin System1 grant state from the parent team.

## Failure Behavior
- Permission denied errors must include:
  - team id
  - system id
  - skill name
  - failed rule category (`team_envelope`, `system_grant`, `system_skill_limit`)
- Denials must be logged for audit.
- For execution denials, use `team_envelope` and `system_grant` only.
- For grant mutation denials, `system_skill_limit` may be returned.

## Data and API Requirements
- Persist team envelope and system grants in Casbin policies (or Casbin-backed adapter tables).
- Provide service-layer APIs to:
  - get/set team envelopes
  - get/set system grants
  - evaluate executable skill list for a specific system
- Service references:
  - `src/cyberagent/services/teams.py`
  - `src/cyberagent/services/systems.py`

## Security Requirements
- Enforce least privilege by default (no implicit grants).
- No wildcard grants except root-admin policies.
- Changes to permission policies must be auditable with actor identity and timestamp.

## Audit and Observability
- Emit structured events for permission CRUD and execution checks.
- Track:
  - who changed policy
  - what changed
  - when changed
  - why denied/allowed

## Testing Requirements
- Unit tests:
  - team envelope checks
  - system grant checks
  - max-5 enforcement
  - root team bypass behavior
- Integration tests:
  - System5 grant/revoke flows
  - execution denied when envelope/system mismatch
  - execution allowed when all checks pass

## Acceptance Criteria
- System cannot execute ungranted skill even if team allows it.
- System cannot execute skill not in team envelope even if directly granted.
- System5 cannot assign disallowed skills.
- Attempt to assign a 6th skill fails deterministically.
- Root team can assign and execute any supported skill.
- Recursed sub-team permissions always match the originating System1 in the parent team.
- Permission updates to the originating System1 propagate to all recursive descendants.

## Clarifications and Locked Decisions (2026-02-02)

### Root Team Identity
- Root team is the default team created on first VSM startup.
- Root team contains exactly one System1, System2, System3, System4, and System5 instance.

### Recursion Permission Inheritance
- A recursed sub-team has a stable linkage to its origin System1 in the parent team.
- Permission enforcement for a recursed sub-team must include the origin System1 grants.
- The parent team remains the authority for permission changes of the origin System1.

### Casbin Modeling Strategy
- Implement a dedicated Casbin model for skill permissions (separate from current generic tool RBAC model).
- Keep one policy shape and perform two explicit checks in service/runtime code:
  - Team envelope check
  - System grant check
- Use deny reason priority: `team_envelope` before `system_grant`.

### Skill Limit Enforcement
- Max-5 rule is enforced only during grant mutation (create/add operations), not during execution checks.

### Envelope Revoke Behavior
- Revoking a skill from the team envelope must revoke matching system grants in that same team.

### Error Contract Scope
- Permission updates only change permissions; no additional side effects.
- Error codes are out of scope for this phase.

### Storage Flexibility
- Casbin remains source of truth.
- Implementation may use Casbin policies and/or Casbin-backed adapter tables per best practice.

### Authority Boundary
- System5 must call service-layer APIs only.
- Service references remain:
  - `src/cyberagent/services/teams.py`
  - `src/cyberagent/services/systems.py`

## Implementation Blueprint

### 1) New Casbin model file
- Add `src/rbac/skill_permissions_model.conf` with:

```ini
[request_definition]
r = sub, team, skill, act

[policy_definition]
p = sub, team, skill, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = (r.sub == p.sub) && (r.team == p.team) && (r.skill == p.skill) && (r.act == p.act)
```

### 2) Subject and resource conventions
- Team envelope subject: `team:{team_id}`
- System grant subject: `system:{system_id}`
- Skill resource: `skill:{skill_name}`
- Action: `allow`

### 3) Evaluation order (runtime/service)
1. Resolve `team_id`, `system_id`, `skill_name`.
2. If root team, allow (global bypass).
3. Check envelope:
   - `enforce("team:{team_id}", "{team_id}", "skill:{skill_name}", "allow")`
   - If false: deny category `team_envelope`.
4. Check system grant:
   - `enforce("system:{system_id}", "{team_id}", "skill:{skill_name}", "allow")`
   - If false: deny category `system_grant`.
5. If system is a recursed sub-team, also require origin System1 grant from parent team:
   - `enforce("system:{origin_system_id}", "{parent_team_id}", "skill:{skill_name}", "allow")`
   - If false: deny category `system_grant`.
6. Allow execution.

### 4) Service API signatures
- `src/cyberagent/services/teams.py`
  - `def list_allowed_skills(team_id: int) -> list[str]: ...`
  - `def add_allowed_skill(team_id: int, skill_name: str, actor_id: str) -> bool: ...`
  - `def remove_allowed_skill(team_id: int, skill_name: str, actor_id: str) -> int: ...`
    - Returns number of revoked system grants in cascade.
  - `def set_allowed_skills(team_id: int, skill_names: list[str], actor_id: str) -> None: ...`

- `src/cyberagent/services/systems.py`
  - `def list_granted_skills(system_id: int) -> list[str]: ...`
  - `def add_skill_grant(system_id: int, skill_name: str, actor_id: str) -> bool: ...`
    - Must enforce team envelope + max-5 at grant time.
  - `def remove_skill_grant(system_id: int, skill_name: str, actor_id: str) -> bool: ...`
  - `def set_skill_grants(system_id: int, skill_names: list[str], actor_id: str) -> None: ...`
    - Must reject >5 entries.
  - `def can_execute_skill(system_id: int, skill_name: str) -> tuple[bool, str | None]: ...`
    - Returns `(allowed, deny_category)` where deny category is one of:
      `team_envelope`, `system_grant`, `None`.

### 5) System5 integration contract
- `src/agents/system5.py` performs no direct Casbin mutations.
- System5 calls `teams.py` / `systems.py` services only for CRUD and evaluation.

## Phased Implementation Plan (TDD-Enforced)

### Phase 1: Foundations (RED -> GREEN -> REFACTOR)
- RED: add failing tests for team envelope CRUD, system grant CRUD, deny precedence, and max-5 enforcement.
- GREEN: implement Casbin skill-permissions model + enforcer wrapper and service APIs.
- REFACTOR: normalize error messages and add minimal structured audit events.

### Phase 2: Enforcement Path (RED -> GREEN -> REFACTOR)
- RED: add failing tests for runtime skill execution gating and deny payloads.
- GREEN: wire `can_execute_skill` into CLI skill execution path.
- REFACTOR: align deny categories and logging with PRD requirements.

### Phase 3: Governance Path (RED -> GREEN -> REFACTOR)
- RED: add failing tests for System5 grant/revoke flows and team-scope restrictions.
- GREEN: implement System5 handlers using services only.
- REFACTOR: lock down cross-team mutation checks.

### Phase 4: Recursion Support (RED -> GREEN -> REFACTOR)
- RED: add failing tests for recursion linkage and inherited permissions.
- GREEN: implement recursion linkage persistence and origin-grant enforcement.
- REFACTOR: confirm propagation semantics without duplicate policy writes.

### Phase 5: Hardening and Coverage (RED -> GREEN -> REFACTOR)
- RED: add failing integration tests for full end-to-end flows (root team bypass, cascade revoke, deep recursion).
- GREEN: optimize lookups and add migration/backfill notes if needed.
- REFACTOR: improve observability and audit coverage.

## TDD Plan (RED -> GREEN -> REFACTOR)

### Unit Tests
- `tests/services/test_team_skill_permissions_service.py`
  - add/list/remove team envelope skills
  - remove envelope skill triggers cascade revoke count
  - root team bypass behavior for envelope checks (if implemented in service)

- `tests/services/test_system_skill_permissions_service.py`
  - cannot grant skill outside team envelope
  - cannot grant 6th skill
  - can grant/revoke/list within constraints
  - `can_execute_skill` deny priority returns `team_envelope` before `system_grant`

### Integration Tests
- `tests/integration/test_skill_permissions_system5_flow.py`
  - System5 grant/revoke through services
  - execution denied on envelope/system mismatch
  - execution allowed when both checks pass
  - root team can grant and execute any supported skill

### Runtime Enforcement Tests
- `tests/tools/test_cli_executor_coverage.py`
  - deny when team envelope fails
  - deny when system grant missing
  - allow when both pass
  - denied error includes: `team_id`, `system_id`, `skill_name`, and deny category
