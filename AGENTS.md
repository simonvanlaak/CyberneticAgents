# AGENTS.md

This file provides guidance to AI coding assistants (Codex, Cursor, Aider, Continue, etc.) when working with code in this repository.

When answering questions, respond with high-confidence answers only: verify in code; do not guess.

Always keep this file up-to-date with newest requirements for the agent.

## Unified Workflow (Required)
GitHub Project is the single source of truth for all planning and execution status.

### Global Rules
1. Create a GitHub Project item as soon as work is identified (feature, bug, PRD, technical plan, implementation task).
2. Status lifecycle is strict: `Backlog` -> `In progress` -> `In review` -> `Done`.
3. Do not use docs files as the primary status tracker; statuses live in GitHub Project.
4. Docs that represent planning/spec work must include a GitHub Project item reference.
5. Use atomic commits while implementing a ticket. Never batch unrelated changes.

### Implementation-Only Workflow
1. Create/confirm GitHub Project item.
2. Move to `In progress`.
3. Implement with tests.
4. Commit atomically and link commits to the issue (`#<issue_number>` in commit subject/body).
5. Move item to `In review` and provide test instructions to the user.
6. After user confirms completion, post a short completion comment on the issue summarizing what changed and listing commit SHAs/links.
7. Move item to `Done`.

### Next Open Ticket Command (Required)
- If the user says "work on the next open ticket" (or equivalent), pick the first `Backlog` item in current GitHub Project ordering.
- Move it to `In progress` before making changes.
- If no `Backlog` item exists, report that and stop.

### User-Driven Bug Lifecycle (Required)
1. When a user reports a bug, create a new GitHub Project ticket immediately.
2. When the user asks to work on the next ticket, select the top item in `Backlog`.
3. Move it to `In progress`, complete implementation, and make atomic commits linked to the issue (`#<issue_number>`).
4. Move it to `In review`.
5. Tell the user exactly how to test the change.
6. Wait for user feedback:
   - If user confirms it works, add a short completion comment on the issue with what was done and commit SHAs/links, then move the ticket to `Done`.
   - If it does not work, move it back to `In progress`, fix it, and repeat.

### Reusable `gh project` Commands (Required)
Use these command templates to execute the workflow quickly and consistently.

```bash
# 0) One-time auth/scope check (required for project commands)
gh auth status
gh auth refresh -s project

# 1) Set shared context
OWNER="@me"
PROJECT_NUMBER=1
REPO="simonvanlaak/CyberneticAgents"

# 2) Resolve project + status field IDs (needed for status updates)
PROJECT_ID="$(gh project view "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.id')"
STATUS_FIELD_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .id')"
BACKLOG_OPTION_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .options[] | select(.name=="Backlog") | .id')"
IN_PROGRESS_OPTION_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .options[] | select(.name=="In progress") | .id')"
IN_REVIEW_OPTION_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .options[] | select(.name=="In review") | .id')"
DONE_OPTION_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .options[] | select(.name=="Done") | .id')"

# 3A) Create a draft ticket directly in project (feature/bug/task)
gh project item-create "$PROJECT_NUMBER" --owner "$OWNER" --title "Bug: <title>" --body "<details>"

# 3B) Or create a repo issue and add it to project
ISSUE_URL="$(gh issue create --repo "$REPO" --title "Bug: <title>" --body "<details>")"
gh project item-add "$PROJECT_NUMBER" --owner "$OWNER" --url "$ISSUE_URL"

# 4) Pick next open ticket (first Backlog item in current project ordering)
NEXT_ITEM_ID="$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 200 --format json --jq '.items[] | select(.status=="Backlog") | .id' | head -n1)"
NEXT_ITEM_TITLE="$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 200 --format json --jq '.items[] | select(.status=="Backlog") | .title' | head -n1)"
echo "$NEXT_ITEM_ID | $NEXT_ITEM_TITLE"
NEXT_ISSUE_NUMBER="$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 200 --format json --jq '.items[] | select(.status=="Backlog") | .content.number' | head -n1)"
echo "Issue #$NEXT_ISSUE_NUMBER"

# 5) Move item through lifecycle
# Backlog -> In progress
gh project item-edit --id "$NEXT_ITEM_ID" --project-id "$PROJECT_ID" --field-id "$STATUS_FIELD_ID" --single-select-option-id "$IN_PROGRESS_OPTION_ID"

# In progress -> In review
gh project item-edit --id "$NEXT_ITEM_ID" --project-id "$PROJECT_ID" --field-id "$STATUS_FIELD_ID" --single-select-option-id "$IN_REVIEW_OPTION_ID"

# In review -> Done
gh project item-edit --id "$NEXT_ITEM_ID" --project-id "$PROJECT_ID" --field-id "$STATUS_FIELD_ID" --single-select-option-id "$DONE_OPTION_ID"

# Reopen failed validation (In review -> In progress)
gh project item-edit --id "$NEXT_ITEM_ID" --project-id "$PROJECT_ID" --field-id "$STATUS_FIELD_ID" --single-select-option-id "$IN_PROGRESS_OPTION_ID"

# 6) Commit with issue linkage (required)
git commit -m "fix: <short description> (#$NEXT_ISSUE_NUMBER)"
# Or include a closing keyword when appropriate:
git commit -m "fix: <short description>" -m "Closes #$NEXT_ISSUE_NUMBER"

# 7) On completion, add issue comment summary with commit links/SHAs (required)
ISSUE_NUMBER="$NEXT_ISSUE_NUMBER"
gh issue comment "$ISSUE_NUMBER" --repo "$REPO" --body "Completed: <1-3 bullet summary>. Commits: <sha_or_link_1>, <sha_or_link_2>."

# 8) Quick status checks
gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 200 --format json --jq '.items[] | {id, title, status}'
gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 200 --format json --jq '.items[] | select(.status=="Backlog") | {id, title}'
```

Notes:
- `gh project item-edit` requires `--project-id`, `--field-id`, and the target status option ID for status changes.
- When "next open ticket" is requested, always use the first `Backlog` result from project ordering.
- If no `Backlog` item is found, report that and stop.

## Docs Directory Rules
- `docs/technical/`: technical plans and security notes.
- `docs/features/`: completed feature write-ups.

## Security
Never commit or publish real phone numbers, videos, or live configuration values. Use obviously fake placeholders in docs, tests, and examples.

## Commit Guidelines
1. Every completed code/doc change must be committed in an atomic commit before moving to the next ticket/task.
2. Always commit your own changes immediately after tests/checks pass for that change.
3. Never batch unrelated changes into one commit; keep scope tightly focused.
4. Use concise, action-oriented conventional commit messages (e.g., `cli: add verbose flag to send`).
5. Link each commit to its issue by including `#<issue_number>` in the commit subject or body.
6. Prefer closing keywords (`Closes #<issue_number>`, `Fixes #<issue_number>`) on the final commit that fully resolves the issue.
7. When an issue is complete, add a short `gh issue comment` summarizing what changed and referencing commit SHAs/links.
8. Stage only the files that belong to your change.
9. If any completed change is still uncommitted, create the atomic commit immediately before starting new work.

## Project Architecture

### Technology Stack
- **Framework**: AutoGen Core (Microsoft)
- **LLM**: Groq API (llama-3.3-70b-versatile)
- **RBAC**: Casbin with SQLAlchemy adapter
- **Database**: SQLite (`data/rbac.db`)
- **Pattern**: Factory-based agent instantiation

### Key Components
- `main.py` - Entry point
- `src/cyberagent/core/runtime.py` - Runtime lifecycle
- `src/cyberagent/services/` - Purpose/strategy/initiative/task/team orchestration
- `src/cyberagent/agents/` - Canonical agent implementations
- `src/cyberagent/authz/` - Canonical RBAC/authz implementation
- `src/agents/`, `src/rbac/`, `src/tools/`, `src/registry.py` - compatibility namespaces

### VSM Hierarchy
```
System 5 (Policy) → System 4 (Intelligence) → System 3 (Control) → System 2 (Coordination) → System 1 (Operations)
```

## Testing Guidelines

### Test-Driven Development (TDD) - STRICT ENFORCEMENT
**NO CODE WITHOUT TESTS FIRST**: All new functionality must have failing tests written before implementation.

**TDD Workflow**:
1. **RED**: Write failing test first
2. **GREEN**: Implement minimal code to pass tests
3. **REFACTOR**: Improve code quality while keeping tests green
4. **COMMIT**: Only commit when all tests pass

## Build/Test/Lint Commands
```bash
# Run all tests
python3 -m pytest tests/ -v

# Run tests with coverage
python3 -m pytest tests/ --cov=src --cov-report=term-missing

# Run tests and fail fast
python3 -m pytest tests/ -x

# Run tests with debugging on failure
python3 -m pytest tests/rbac/test_namespace.py -x --pdb
```

### Code Quality
```bash
# Type checking (if mypy is available)
python3 -m mypy src/ --ignore-missing-imports

# Format checking (if black is available)
python3 -m black --check src/ tests/

# Lint checking (if flake8 is available)
python3 -m flake8 src/ tests/
```


## Git Hooks
Git hooks live in `git-hooks/`. Install them by linking or copying into `.git/hooks`:
```bash
ln -sf ../../git-hooks/pre-commit .git/hooks/pre-commit
ln -sf ../../git-hooks/pre-push .git/hooks/pre-push
```
Hooks behavior:
- `pre-commit`: first enforces staged Python file line limits (warning at 700, fail at 1000), then runs `black --check`, `ruff check`, `basedpyright`, and staged `pytest` (with coverage when staged `src/` files exist).
- `pre-push`: first enforces tracked Python file line limits (warning at 700, fail at 1000), then runs `black --check`, `ruff check`, `basedpyright`, and finally the full test suite with coverage.

You have to always pass git-hooks, never use --no-verify.

## Directory Structure (1 level deep)
Hidden/cached dirs omitted (e.g., `.git`, `.venv`, `.pytest_cache`, `__pycache__`).
```
.
├── AGENTS.md
├── LICENSE
├── README.md
├── main.py
├── pyproject.toml
├── data/
├── docs/
├── git-hooks/
│   ├── pre-commit
│   └── pre-push
├── logs/
├── src/
│   ├── agents/
│   ├── cyberagent/
│   │   ├── cli/
│   │   ├── core/
│   │   ├── db/
│   │   ├── domain/
│   │   ├── services/
│   │   └── tools/
│   ├── prompts/
│   ├── rbac/
│   ├── tools/
│   ├── registry.py
│   └── cli_session.py
└── tests/
│   ├── agents/
│   ├── cli/
│   ├── fixtures/
│   ├── registry/
│   └── tools/
```


## Code Style Guidelines
add brief comments for tricky logic; keep files under ~500 LOC when feasible (split/refactor as needed).

### Import Organization
```python
# 1. Standard library
import os
from dataclasses import dataclass

# 2. Third-party (AutoGen, Casbin)
from autogen_core import AgentId, RoutedAgent, message_handler
from casbin import Enforcer

# 3. Local imports
from src.cyberagent.core.runtime import get_runtime
from src.cyberagent.agents.messages import UserMessage
```

## Refactor Conventions (Current)
- `src/cyberagent/` is canonical for runtime, agents, services, and authz.
- Legacy namespaces (`src/agents/`, `src/tools/`, `src/rbac/`, `src/registry.py`) may exist as compatibility entrypoints only.
- Do not remove compatibility paths without updating tests and docs in the same change.

### Type Hints - MANDATORY
All functions must have complete type hints:
```python
from typing import Optional

async def send_message(
    message: UserMessage,
    recipient: AgentId,
    timeout: Optional[int] = None
) -> UserMessage:
    pass
```

### Error Handling
Use specific exceptions with clear messages:
```python
if not allowed:
    raise PermissionError(
        f"Agent '{sender}' is not permitted to delegate to '{recipient}'. "
        f"RBAC policy denies: ({sender}, communication_delegate, {recipient})"
    )
```

### Docstrings - Google Style
```python
def register_vsm_agent_type() -> None:
    """
    Register the VSM agent type with the runtime.
    
    Creates a factory function that instantiates VSMSystemAgent
    instances on-demand when messages are first sent to them.
    
    The factory uses AgentInstantiationContext to get the agent ID.
    """
    pass
```


### Naming Conventions
- **Functions**: `snake_case` - `test_extract_namespace_from_system_id()`
- **Classes**: `PascalCase` - `VSMSystemAgent`
- **Constants**: `UPPER_SNAKE_CASE` - `MAX_RETRIES`
- **Agent IDs**: `namespace_type_name` - `root_control_sys3`


## Environment Variables
defined in .env.example

## CLI Observability (Phase 1)
- Every CLI command summarizes new runtime `WARNING`/`ERROR` log lines since the last command.
- Use `cyberagent logs` to view details.

## Multi-agent safety
do not create/apply/drop git stash entries unless explicitly requested (this includes git pull --rebase --autostash). Assume other agents may be working; keep unrelated WIP untouched and avoid cross-cutting state changes.
when the user says "push", you may git pull --rebase to integrate latest changes (never discard other agents' work). When the user says "commit", scope to your changes only. When the user says "commit all", commit everything in grouped chunks.
do not create/remove/modify git worktree checkouts (or edit .worktrees/*) unless explicitly requested.
do not switch branches / check out a different branch unless explicitly requested.
running multiple agents is OK as long as each agent has its own session.
when you see unrecognized files, keep going; focus on your changes and commit only those.
only stage your changes when you are about to commit.

Unexpected/unrelated working-tree changes (required behavior):
- Do **not** stop work just because unrelated files changed.
- Leave unrelated files untouched and unstaged.
- Do **not** revert unrelated changes unless explicitly asked.
- Commit only files for your current ticket.
- If unrelated files are already staged, unstage them first, commit your own files, then re-stage the unrelated files.

focus reports on your edits; avoid guard-rail disclaimers unless truly blocked; when multiple agents touch the same file, continue if safe; end with a brief “other files present” note only if relevant.

## Dependencies
1. Ensure the `pyproject.toml` dependencies always reflect the required packages for the project
2. If dependencies are missing install them in a virtual environment from `pyproject.toml`
3. If new dependencies are required, modify `pyproject.toml` first.

## Debug Mode
When you receive an error message you should get into debug mode.
During debug mode you repeat the following:
1. Decide if a test should be written to reproduce the error provided, and create them if needed.
2. Fix the provided error
3. Re run the command that threw the error before
4. If the command still throws an error, repeat this. If no errors are throw. Commit the changes and exit this loop.
