# AGENTS.md

This file provides guidance to AI coding assistants (Codex, Cursor, Aider, Continue, etc.) when working with code in this repository.

When answering questions, respond with high-confidence answers only: verify in code; do not guess.

Always keep this file up-to-date with newest requirements for the agent.

## Security
Never commit or publish real phone numbers, videos, or live configuration values. Use obviously fake placeholders in docs, tests, and examples.

## Commit Guidelines
Follow concise, action-oriented commit messages (e.g., CLI: add verbose flag to send). And conventional commits. Make commits contain a small amount of code changes following the atomic commit principle.

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
- `src/agents/` - Agent implementations (legacy path, still active during refactor)
- `src/rbac/` - RBAC configuration (legacy path, still active during refactor)
- `src/registry.py` - Agent registration bridge

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
- `pre-commit`: runs `black --check` on staged Python files and `pytest` on staged test files.
- `pre-push`: runs the full test suite (`python3 -m pytest tests/ -v`).

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
from src.agents.messages import UserMessage
```

## Refactor Conventions (Current)
- Prefer new code under `src/cyberagent/` unless a legacy path is explicitly required.
- Keep `src/agents/`, `src/tools/`, `src/rbac/`, and `src/registry.py` stable until migration completion.
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
only stage your changes, when you are about to commit them.
when you see unrecognized or unrelated changes, proceed without asking; do not revert them and do not stage them unless explicitly requested.
if unexpected changes are already staged, unstage them, commit only your changes, then re-stage the unexpected changes.
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
