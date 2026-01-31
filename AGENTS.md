# AGENTS.md

This file provides guidance to AI coding assistants (Codex, Cursor, Aider, Continue, etc.) when working with code in this repository.

When answering questions, respond with high-confidence answers only: verify in code; do not guess.

Always keep this file up-to-date with newest requirements for the agent.

## Security
Never commit or publish real phone numbers, videos, or live configuration values. Use obviously fake placeholders in docs, tests, and examples.

## Commit Guidelines
Follow concise, action-oriented commit messages (e.g., CLI: add verbose flag to send).

## Project Architecture

### Technology Stack
- **Framework**: AutoGen Core (Microsoft)
- **LLM**: Groq API (llama-3.3-70b-versatile)
- **RBAC**: Casbin with SQLAlchemy adapter
- **Database**: SQLite (`data/rbac.db`)
- **Pattern**: Factory-based agent instantiation

### Key Components
- `main.py` - Entry point
- `src/agents/vsm_agent.py` - VSMSystemAgent implementation
- `src/rbac/` - RBAC configuration
- `src/registry.py` - Agent registration
- `src/tools/system_create.py` - Programmatic policy creation

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


## Directory Structure (1 level deep)
Hidden/cached dirs omitted (e.g., `.git`, `.venv`, `.pytest_cache`, `__pycache__`).
```
.
├── AGENTS.md
├── LICENSE
├── README.md
├── main.py
├── requirements.txt
├── data/
├── docs/
├── git-hooks/
│   ├── pre-commit
│   └── pre-push
├── logs/
├── src/
│   ├── agents/
│   ├── cli/
│   ├── models/
│   ├── prompts/
│   ├── rbac/
│   ├── tools/
└── tests/
│   ├── agents/
│   ├── cli/
│   ├── fixtures/
│   ├── models/
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
from src.runtime import get_runtime
from src.agents import DelegateMessage
```

### Type Hints - MANDATORY
All functions must have complete type hints:
```python
from typing import Optional, List, Dict, Any

async def send_message(
    message: DelegateMessage,
    recipient: AgentId,
    timeout: Optional[int] = None
) -> DelegateMessage:
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

## Multi-agent safety
do not create/apply/drop git stash entries unless explicitly requested (this includes git pull --rebase --autostash). Assume other agents may be working; keep unrelated WIP untouched and avoid cross-cutting state changes.
when the user says "push", you may git pull --rebase to integrate latest changes (never discard other agents' work). When the user says "commit", scope to your changes only. When the user says "commit all", commit everything in grouped chunks.
do not create/remove/modify git worktree checkouts (or edit .worktrees/*) unless explicitly requested.
do not switch branches / check out a different branch unless explicitly requested.
running multiple agents is OK as long as each agent has its own session.
when you see unrecognized files, keep going; focus on your changes and commit only those.
focus reports on your edits; avoid guard-rail disclaimers unless truly blocked; when multiple agents touch the same file, continue if safe; end with a brief “other files present” note only if relevant.

## Dependencies
1. Ensure the ./requirements.txt file always reflects the required dependencies for the project
2. If dependencies are missing install them in a virtual environment from ./requirements.txt
3. If new dependencies are required, modify the ./requirements.txt file first.
