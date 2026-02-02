# Skill Permissions PRD

## Document Status
- Status: Draft (implementation-ready)
- Owner: Platform/Security
- Last updated: 2026-02-02

## Purpose
Define the permission model and enforcement requirements for agent skills, including team-level envelopes, system-level grants, and System5 governance flows.

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

## Enforcement Flow
1. Agent requests skill execution.
2. Runtime resolves team id + system id.
3. Casbin check verifies system grant for the skill.
4. Casbin check verifies team envelope allows that skill.
5. Runtime checks system grant count limit (<= 5).
6. Execution proceeds only if all checks pass.

## Failure Behavior
- Permission denied errors must include:
  - team id
  - system id
  - skill name
  - failed rule category (`team_envelope`, `system_grant`, `system_skill_limit`)
- Denials must be logged for audit.

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
