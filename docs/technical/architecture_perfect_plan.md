# Perfect Architecture Plan

This document describes the target architecture for CyberneticAgents and a phased plan to reach it with minimal disruption.

## Goals
- Clarify module boundaries and dependency direction.
- Keep domain logic isolated from infrastructure.
- Make tests faster and more deterministic.
- Keep the public CLI stable while reorganizing internals.
- Support the VSM hierarchy cleanly (System 1–5 + User).

## Target Directory Layout
```
.
├── main.py
├── src/
│   ├── cyberagent/                # Top-level package namespace
│   │   ├── __init__.py
│   │   ├── agents/                # System1–5, User agent implementations
│   │   ├── cli/                   # CLI entry points + parsers
│   │   ├── core/                  # App core (runtime, state, logging, config)
│   │   ├── db/                    # DB session, migrations, init, models base
│   │   ├── domain/                # Pure domain models + business logic
│   │   ├── prompts/               # Prompt templates (by system)
│   │   ├── rbac/                  # Enforcer, policies, RBAC adapters
│   │   ├── services/              # Orchestration services (strategy, tasks)
│   │   ├── tools/                 # Agent tools (system_create, delegate, etc.)
│   │   ├── ui/                    # Optional TUI/GUI components (if present)
│   │   └── utils/                 # Shared helpers (small, dependency-light)
│   └── vendor/                    # Third-party vendored code (if needed)
├── tests/
│   ├── agents/
│   ├── cli/
│   ├── core/
│   ├── db/
│   ├── domain/
│   ├── rbac/
│   ├── services/
│   ├── tools/
│   └── ui/
├── docs/
│   └── architecture_perfect_plan.md
├── data/                          # Runtime DBs (gitignored)
├── logs/                          # Runtime logs (gitignored)
└── requirements.txt
```

## Module Responsibilities
- `agents/`: VSM agent classes and message handlers only.
- `core/`: runtime orchestration, tracing, app state, logging setup, config.
- `db/`: `init_db`, session management, migrations, and SQLAlchemy Base.
- `domain/`: domain entities and business rules (no I/O).
- `services/`: app use-cases that coordinate domain + db + tools.
- `tools/`: tool adapters used by agents; minimal logic here.
- `rbac/`: RBAC enforcement and policy management.
- `prompts/`: static prompt templates with clear naming.
- `ui/`: optional UI; if not used, remove tests and code cleanly.

## Dependency Direction (Rules)
- `domain/` has **no dependencies** on db, cli, agents, or tools.
- `services/` depends on `domain/`, `db/`, `rbac/`, `tools/`.
- `agents/` depends on `services/`, `domain/`, `tools/`, `rbac/`.
- `cli/` depends on `services/` and `core/`, not on agents directly.
- `core/` depends on `db/`, `rbac/`, `services/`, and infra utilities.
- `ui/` depends on `services/` and `core/`, not on agents directly.

## Configuration & Runtime
- All environment configuration loaded in `core/config.py`.
- `core/runtime.py` owns startup/teardown and exposes a stable API.
- `db/session.py` provides session management and context helpers.

## Naming & Public API
- Expose stable imports via `src/cyberagent/__init__.py`.
- Old import paths re-exported temporarily during migration.

## Tests
- Each top-level package has a matching test namespace.
- Domain tests do not touch the database.
- DB integration tests live under `tests/db/`.

## Migration Plan (Phased)
1. **Create package root**: introduce `src/cyberagent/` and re-export existing modules.
2. **Move core/db**: migrate `init_db`, `db_utils`, `team_state`, `runtime`, logging.
3. **Move domain**: move SQLAlchemy models into `db/` and pure logic into `domain/`.
4. **Refactor services**: add service layer to centralize orchestration logic.
5. **Simplify tools**: tools become thin wrappers around services.
6. **Clean UI**: either restore `ui/` or delete UI tests and references.
7. **Finalize imports**: remove legacy re-exports once all imports updated.

## Non-Goals
- No behavior change during structural moves.
- No new dependencies unless necessary for migration tooling.

## Success Criteria
- Clear ownership of responsibilities per package.
- Faster tests by isolating domain logic.
- Predictable dependency tree without cycles.
- CLI and agent workflows unchanged from a user perspective.
