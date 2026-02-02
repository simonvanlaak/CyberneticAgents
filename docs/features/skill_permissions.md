# Skill Permissions Feature

## Overview
Skill permissions control which CLI skills each team and system can execute. System 5 governs grants, team envelopes define the allowed skill set, and runtime enforcement blocks execution when policy or recursion inheritance rules fail.

## Core Capabilities
- **Team envelope**: Allowed skills per team, managed by System 5.
- **System grants**: Per-system executable skills, capped at 5.
- **Recursion inheritance**: Recursed sub-teams inherit grants from the origin System 1, while still acting like System 1 to the parent team.
- **Root bypass**: Root team can grant/execute any supported skill.
- **Runtime enforcement**: Denied executions return structured error fields for debugging.
- **Audit logs**: Permission CRUD and execution decisions emit structured audit events.

## Permission Model Summary
- Team envelope controls which skills are even eligible.
- System grants are a subset of the team envelope.
- Max 5 system grants enforced on add/set.
- Recursion links map sub-team -> origin system + parent team.

## Runtime Behavior
- `CliTool.execute` checks RBAC, then skill permissions.
- Denies return `team_id`, `system_id`, `skill_name`, and `failed_rule_category`.
- Execution success requires both envelope and grant checks to pass.

## How to Test
Quick targets:
- `python3 -m pytest tests/services/test_team_skill_permissions_service.py tests/services/test_system_skill_permissions_service.py -v`
- `python3 -m pytest tests/integration/test_skill_permissions_integration.py -v`
- `python3 -m pytest tests/tools/test_cli_executor_coverage.py -v`

## File Map
- Services:
  - `src/cyberagent/services/teams.py`
  - `src/cyberagent/services/systems.py`
  - `src/cyberagent/services/recursions.py`
- System 5 handlers:
  - `src/agents/system5.py`
- Enforcement:
  - `src/cyberagent/tools/cli_executor/cli_tool.py`
  - `src/rbac/skill_permissions_enforcer.py`
- Tests:
  - `tests/services/test_team_skill_permissions_service.py`
  - `tests/services/test_system_skill_permissions_service.py`
  - `tests/integration/test_skill_permissions_integration.py`
  - `tests/agents/test_system5_skill_permissions.py`
