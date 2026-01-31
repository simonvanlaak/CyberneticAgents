# CyberneticAgents

A VSM-inspired multi-agent system built on AutoGen Core + AgentChat, with Casbin RBAC and a Textual TUI. The project models Systems 1/3/4/5 as agent roles and routes messages through tools guarded by RBAC policies, with optional Langfuse tracing.

## What This Is (Current State)

- **Multi-agent runtime** using AutoGen Core + AgentChat
- **VSM agent roles**: System 1, 3, 4, 5 (System 2 is defined in RBAC types but not implemented yet)
- **RBAC enforcement** via Casbin for tool use and cross-agent actions
- **Task/initiative/policy data model** backed by SQLite (SQLAlchemy)
- **Textual TUI** and headless CLI mode for interacting with the system
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
# Textual TUI
python main.py

# Headless (no TUI)
python main.py --headless "hello"
```

## Headless CLI (experimental)

- The Textual UI is disabled for now; use `cyberagent start` to boot the VSM in headless mode instead of the old UI entry point.
- `cyberagent status` shows the active strategy/task hierarchy, while `cyberagent suggest` lets you pipe JSON/YAML payloads into System 4.
- Observability helpers (`cyberagent logs`, `cyberagent inbox`, `cyberagent watch`) and the `cyberagent login` command (which stores a keyring-backed token) round out the current CLI surface.

## Project Structure (Current)

```
CyberneticAgents/
├── main.py                     # Entry point (TUI + headless)
├── .env.example                # Example env config
├── data/                       # Runtime databases (created locally)
│   ├── CyberneticAgents.db     # SQLAlchemy app data
│   └── rbac.db                 # Casbin RBAC policies
├── src/
│   ├── agents/                 # System 1/3/4/5 + UserAgent
│   ├── prompts/                # System prompts (1-5)
│   ├── rbac/                   # Casbin enforcer + model
│   ├── tools/                  # RBAC-guarded tools
│   ├── ui/                     # Textual TUI
│   ├── models/                 # SQLAlchemy models
│   ├── registry.py             # Agent factory registration
│   ├── runtime.py              # Runtime + tracing setup
│   └── ...
├── tests/                      # pytest suite
├── docs/                       # Project notes/roadmap
└── requirements.txt
```

## How It Works (High Level)

- `main.py` initializes databases and registers agent factories.
- `UserAgent` receives user input and forwards it to System 4.
- System agents coordinate tasks and policies through tools.
- Tools validate actions via RBAC (Casbin) before executing.
- Messages and tool usage are logged into the UI, with optional tracing.

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
- Improve UI workflow and observability

## License

MIT. See `LICENSE`.
