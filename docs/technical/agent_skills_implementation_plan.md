# Agent Skills Implementation Plan (Phase 1 + Phase 5 + Unit Tests)

## Scope for This Iteration
- Include only Phase 1 (skill registry/contracts), Phase 5 (secrets + PKM read-only), and unit-test coverage.
- Defer permission CRUD flows, System5 policy tooling, and integration tests to later iterations.

## Phase 1 - Skill Registry and Contracts

### Objectives
- Add Agent Skills-compatible skill packages under `skills/*/SKILL.md`.
- Implement metadata-first skill discovery with progressive disclosure.
- Create AutoGen tool wrappers from loaded skills.

### Deliverables
1. Skill package structure:
   - `src/tools/skills/web-search/SKILL.md`
   - `src/tools/skills/web-fetch/SKILL.md`
   - `src/tools/skills/file-reader/SKILL.md`
   - `src/tools/skills/git-readonly-sync/SKILL.md`
2. Skill metadata loader:
   - `src/cyberagent/tools/cli_executor/skill_loader.py`
   - Parse YAML frontmatter from `SKILL.md`.
   - Validate required fields (`name`, `description`).
   - Expose metadata for runtime loading.
3. AutoGen tool builder:
   - `src/cyberagent/tools/cli_executor/skill_tools.py`
   - Create `FunctionTool` instances backed by `CliTool.execute`.
   - Map each skill to a callable tool name and JSON argument payload.

### Architecture Notes
- Startup path should load only metadata from `SKILL.md`.
- Full instructions should be loaded on demand via `load_skill_instructions`.
- Skill execution flows through existing `src/cyberagent/tools/cli_executor/cli_tool.py`.

## Phase 5 - Secrets and PKM Read-Only Runtime

### Objectives
- Keep 1Password as mandatory secret source.
- Ensure runtime supports read-only repository and file analysis workflows.
- Prepare a single Docker base image with required CLIs.

### Deliverables
1. Docker image definition:
   - `src/cyberagent/tools/cli_executor/Dockerfile.cli-tools`
   - Includes:
     - Brave Search CLI
     - Readability-based fetch CLI/runtime support
     - File reading tools
     - Git for public repository cloning
2. Secrets contract:
   - Continue fail-closed behavior from `src/cyberagent/tools/cli_executor/secrets.py`.
   - No credential persistence in files.
3. PKM skill posture:
   - `git-readonly-sync` and `file-reader` remain read-only by contract in SKILL docs.

### Architecture Notes
- Single image now; manually evaluate split when image approaches/exceeds 500 MB.
- Keep executor environment injection process-scoped per command.

## Unit Test Plan

### New Unit Tests
1. `tests/tools/test_skill_loader.py`
   - Loads valid skill frontmatter.
   - Reads full skill instructions on demand.
   - Rejects missing required fields.
2. `tests/tools/test_skill_tool_factory.py`
   - Builds AutoGen tools from skill metadata.
   - Verifies generated tool invokes `CliTool.execute` with expected arguments.

### Existing Unit Tests to Keep Green
- `tests/tools/test_cli_tool_env.py`
- `tests/tools/test_cli_tool_secrets.py`
- `tests/tools/test_cli_executor_coverage.py`

### Test Commands
```bash
python3 -m pytest tests/tools/test_skill_loader.py tests/tools/test_skill_tool_factory.py -v
python3 -m pytest tests/tools/test_cli_tool_env.py tests/tools/test_cli_tool_secrets.py tests/tools/test_cli_executor_coverage.py -v
```
