# CyberneticAgents

A VSM-inspired multi-agent system built on AutoGen Core + AgentChat with Casbin RBAC. The project models Systems 1/3/4/5 as agent roles and routes messages through tools guarded by RBAC policies, with optional Langfuse tracing.

## What This Is (Current State)

- **Multi-agent runtime** using AutoGen Core + AgentChat
- **VSM agent roles**: System 1, 3, 4, 5 (System 2 is defined in RBAC types but not implemented yet)
- **RBAC enforcement** via Casbin for cross-agent actions
- **Task/initiative/policy data model** backed by SQLite (SQLAlchemy)
- **CLI-first interaction** for working with the system
- **Optional tracing** with Langfuse via OpenTelemetry

## Quick Start

### 1) Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure

Copy `.env.example` to `.env` and fill in at least:

```bash
GROQ_API_KEY=your_groq_api_key_here
```

Optional (for tracing):

```bash
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

### 3) Run

```bash
# Interactive CLI session
python main.py

# Send an initial message
python main.py --message "hello"
```

## CLI (primary)

- Install the CLI entrypoint (uv):
```bash
uv tool install -e .
```
- Run the CLI:
```bash
cyberagent start
```

- Use `cyberagent start` to boot the VSM runtime in the background for CLI workflows.
- `cyberagent status` shows the active strategy/task hierarchy, while `cyberagent suggest` lets you pipe JSON/YAML payloads into System 4.
- Observability helpers (`cyberagent logs`, `cyberagent inbox`, `cyberagent watch`) and the `cyberagent login` command (which stores a keyring-backed token) round out the current CLI surface.
- Each CLI command summarizes any new runtime `WARNING`/`ERROR` logs since the last command; run `cyberagent logs` for details.

## Project Structure (Current Transitional Layout)

```
CyberneticAgents/
├── main.py                     # Entry point (CLI)
├── .env.example                # Example env config
├── data/                       # Runtime databases (created locally)
│   ├── CyberneticAgents.db     # SQLAlchemy app data
│   └── rbac.db                 # Casbin RBAC policies
├── src/
│   ├── cyberagent/             # New package namespace (refactor target)
│   │   ├── cli/                # CLI entry points (`cyberagent`, headless, status)
│   │   ├── core/               # Runtime, logging, shared state
│   │   ├── db/                 # DB init and DB utility layer
│   │   ├── domain/             # Domain-level specs and serialization
│   │   ├── services/           # Purpose/strategy/initiative/task/team services
│   │   └── tools/              # Refactored tool namespace package
│   ├── agents/                 # Active agent implementations (legacy path, in transition)
│   ├── prompts/                # System prompts (1-5)
│   ├── rbac/                   # Casbin enforcer + model (legacy path, in transition)
│   ├── tools/                  # Tool adapters still under migration
│   ├── registry.py             # Agent factory registration (legacy entry point)
│   ├── cli_session.py          # CLI question/answer queue state
│   ├── llm_config.py           # LLM client setup
│   └── ...
├── tests/                      # pytest suite
├── docs/                       # Project notes/roadmap
└── requirements.txt
```

## How It Works (High Level)

- `main.py` routes into the headless CLI runtime (`src/cyberagent/cli/headless.py`).
- The headless runtime initializes DB state and registers agent factories.
- `UserAgent` receives user input and forwards it to System 4.
- System agents coordinate tasks and policies via internal workflows and CLI tooling.
- CLI tools are executed through a Docker CLI executor when configured.
- Messages and tool usage are logged to stdout and runtime logs, with optional tracing.

## Known Transitional Modules

Until the refactor is fully complete, these legacy paths are still intentionally active:
- `src/agents/`
- `src/tools/`
- `src/rbac/`
- `src/registry.py`

## Development

### Tests

```bash
python3 -m pytest tests/ -v
```

### Pre-commit

```bash
pre-commit install
pre-commit run --all-files
```

## Roadmap (Short)

- Implement System 2 (coordination) agent
- Expand tool coverage and RBAC policies
- Improve CLI workflow and observability

## License

MIT. See `LICENSE`.
