# AGENTS.md

This file provides guidance to AI coding assistants (Cursor, Aider, Continue, etc.) when working with code in this repository.

## Build/Test/Lint Commands

### Testing (TDD - MANDATORY)
```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/rbac/test_namespace.py -v

# Run specific test function
python3 -m pytest tests/rbac/test_namespace.py::test_extract_namespace_from_system_id -vv

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

## Code Style Guidelines

### Test-Driven Development (TDD) - STRICT ENFORCEMENT
**NO CODE WITHOUT TESTS FIRST**: All new functionality must have failing tests written before implementation.

**TDD Workflow**:
1. **RED**: Write failing test first
2. **GREEN**: Implement minimal code to pass tests
3. **REFACTOR**: Improve code quality while keeping tests green
4. **COMMIT**: Only commit when all tests pass

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

### Naming Conventions
- **Functions**: `snake_case` - `test_extract_namespace_from_system_id()`
- **Classes**: `PascalCase` - `VSMSystemAgent`
- **Constants**: `UPPER_SNAKE_CASE` - `MAX_RETRIES`
- **Agent IDs**: `namespace_type_name` - `root_control_sys3`

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

## Development Workflow

### Adding New Agents
```python
from src.tools.system_create import create_system

# Creates system with automatic RBAC policies
create_system(namespace="root", system_type="operations", name="new_agent")

# Send task (auto-creates on first message)
result = await send_task_to_agent(
    target_id="root_operations_new_agent",
    task="Execute task",
    source_id="user"
)
```

### Adding Message Types
1. Define dataclass in `src/agents/vsm_agent.py`
2. Add message handler with `@message_handler`
3. Export in `src/agents/__init__.py`

## Environment Variables
```bash
# Required
export GROQ_API_KEY='your-key'  # pragma: allowlist secret

# Optional
export MISTRAL_API_KEY='your-mistral-key'  # pragma: allowlist secret
```

## Quick Debugging
```python
# Test RBAC permissions
from src.rbac.enforcer import get_enforcer
enforcer = get_enforcer()
allowed = enforcer.enforce("sender_id", "namespace", "tool", "target_id")

# Check namespace extraction
from src.rbac.enforcer import extract_namespace_from_system_id
namespace = extract_namespace_from_system_id("myapp_operations_worker")
```
