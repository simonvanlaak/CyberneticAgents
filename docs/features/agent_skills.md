# Agent Skills Feature

## Overview
Agent skills provide a standardized, safe way for VSM agents to discover and execute capabilities via CLI tools running in a shared Docker image. Skills are defined using the Agent Skills `SKILL.md` contract and are governed by team/system permissions with strict secret handling.

## Core Capabilities
- **Skill packaging**: Each skill lives under `src/tools/skills/<skill-name>/SKILL.md` with YAML frontmatter and Markdown instructions.
- **Progressive disclosure**: Runtime loads metadata first (name/description/schema/etc.), loads full instructions on demand.
- **CLI execution**: Skills run in a Docker-backed CLI executor with per-skill timeouts and stdout/stderr capture.
- **Secrets**: Required secrets are injected via 1Password-only environment variables. Execution fails closed when secrets are missing.
- **Permissions**: Team envelopes define allowed skills; system grants define executable skills. Max 5 skills per system enforced at grant time.
- **Audit logging**: Permission CRUD and decisions emit structured audit logs.
- **PKM read-only sync**: A `git-readonly-sync` CLI supports cloning/pulling repositories without write operations.
- **Spec compliance**: Skill name/description validation, schema validation, and optional `skills-ref validate` integration.

## Skill Metadata Contract
Required frontmatter fields:
- `name`
- `description`

Supported metadata fields:
- `metadata.cyberagent.tool`
- `metadata.cyberagent.subcommand`
- `metadata.cyberagent.required_env`
- `metadata.cyberagent.timeout_class` (`short`, `standard`, `long`)
- `input_schema` (JSON schema-like mapping)
- `output_schema` (JSON schema-like mapping)

Name rules:
- 1–64 chars, lowercase letters/numbers/hyphens only
- no leading/trailing or consecutive hyphens
- must match the parent directory name

## Runtime Behavior
- **Tool loading**: Skills are filtered by system grants and capped at 5 tools.
- **Prompt injection**: Tool metadata includes name, description, input/output keys, timeout class, required secrets, and location.
- **Execution**: Calls `CliTool.execute` with:
  - permission checks (team/system + recursion inheritance)
  - per-skill timeout override
  - environment injection (secrets)
  - stdout/stderr capture in result payload

## Permission Model Summary
- Team envelope controls which skills are allowed for a team.
- System grants define which skills a system can execute.
- Root team bypasses envelope checks.
- Recursed sub-teams inherit grants from origin System1.
- Max 5 grants per system enforced on add/set.

## CLI Tools in Base Image
- `brave-search` (web search)
- `web-fetch` (readability extraction)
- `git-readonly-sync` (clone/pull read-only)

## How to Test
Quick test targets:
- `python3 -m pytest tests/tools/ -v`
- `python3 -m pytest tests/services/test_team_skill_permissions_service.py tests/services/test_system_skill_permissions_service.py -v`
- `python3 -m pytest tests/integration/test_cli_tools_integration.py -v`

Skills validator (requires `skills-ref`):
```
python3 - <<'PY'
from src.cyberagent.tools.cli_executor.skill_validation import validate_skills
validate_skills("src/tools/skills")
print("skills-ref validation OK")
PY
```

## File Map
- Skill loader/runtime/tools:
  - `src/cyberagent/tools/cli_executor/skill_loader.py`
  - `src/cyberagent/tools/cli_executor/skill_runtime.py`
  - `src/cyberagent/tools/cli_executor/skill_tools.py`
- Executor and secrets:
  - `src/cyberagent/tools/cli_executor/cli_tool.py`
  - `src/cyberagent/tools/cli_executor/docker_env_executor.py`
  - `src/cyberagent/tools/cli_executor/secrets.py`
- Permissions:
  - `src/cyberagent/services/teams.py`
  - `src/cyberagent/services/systems.py`
  - `src/rbac/skill_permissions_enforcer.py`
- Skills:
  - `src/tools/skills/web-search/SKILL.md`
  - `src/tools/skills/web-fetch/SKILL.md`
  - `src/tools/skills/file-reader/SKILL.md`
  - `src/tools/skills/git-readonly-sync/SKILL.md`
- Docker image:
  - `src/cyberagent/tools/cli_executor/Dockerfile.cli-tools`
