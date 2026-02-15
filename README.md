# CyberneticAgents

CyberneticAgents is a VSM-inspired multi-agent system built with AutoGen Core, Casbin RBAC, and a CLI-first runtime.

It models Systems 1/3/4/5 as cooperating agents and enforces role boundaries for cross-agent actions.

## Current status

- Multi-agent runtime (AutoGen Core + AgentChat)
- VSM roles implemented: System 1, 3, 4, 5
- Casbin RBAC enforcement for delegation/tool actions
- SQLite-backed domain data and policy data
- CLI-first workflows, optional Telegram interaction
- Label-driven GitHub issue automation for implementation flow

---

## Quick start

## Prerequisites

- Python 3.11+
- Docker (required for tool/skill execution)
- 1Password CLI (`op`) with access to required secrets

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

(Optional) install CLI entrypoint with uv:

```bash
uv tool install -e .
```

## Configure secrets

CyberneticAgents expects secrets from 1Password at runtime.
Create a vault named `CyberneticAgents` and add items (with a `credential` field):

- `GROQ_API_KEY` (required)
- `BRAVE_API_KEY` (required for web search)
- `MISTRAL_API_KEY` (only if `LLM_PROVIDER=mistral`)
- optional: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGSMITH_API_KEY`
- optional: `TELEGRAM_BOT_TOKEN`

Sign in to 1Password in your shell:

```bash
eval "$(op signin --account <shorthand>)"
```

Copy and adjust local env config:

```bash
cp .env.example .env
```

---

## Run the system

## Onboarding

```bash
cyberagent onboarding
```

Onboarding validates environment/dependencies and prepares runtime capabilities.

## Start runtime

```bash
cyberagent start
```

Useful commands:

```bash
cyberagent status
cyberagent restart
cyberagent logs
cyberagent inbox
cyberagent watch
cyberagent suggest
```

If `TELEGRAM_BOT_TOKEN` is configured, onboarding/user interaction can run through Telegram.

---

## Automation workflow (source of truth)

This repo uses **GitHub Issue stage labels** as the implementation workflow source of truth.

Use exactly one stage label per issue:

- `stage:backlog`
- `stage:needs-clarification`
- `stage:ready-to-implement`
- `stage:in-progress`
- `stage:in-review`
- `stage:blocked`

### Canonical automation entrypoints

- `./scripts/run_project_automation.sh`
  - singleton lock + repo-root guard
- `./scripts/cron_cyberneticagents_worker.sh`
  - issue stage worker
- `./scripts/quality_gate.sh`
  - required quality gate before review/push

**No GitHub Projects v2 queue is used for active automation flow.**

---

## Architecture and directory layout

```text
CyberneticAgents/
├── main.py
├── pyproject.toml
├── data/
├── docs/
├── scripts/
├── src/
│   ├── cyberagent/
│   │   ├── cli/
│   │   ├── core/
│   │   ├── db/
│   │   ├── domain/
│   │   ├── services/
│   │   └── tools/
│   ├── agents/        # legacy path (still active during migration)
│   ├── rbac/          # legacy path (still active during migration)
│   ├── tools/         # legacy path (still active during migration)
│   └── registry.py    # legacy bridge
└── tests/
```

Legacy paths above remain active until migration completes.

---

## Testing and quality gates

Run tests:

```bash
python3 -m pytest tests/ -v
```

Coverage run:

```bash
python3 -m pytest tests/ --cov=src --cov-report=term-missing
```

Required automation gate:

```bash
bash ./scripts/quality_gate.sh
```

Git hooks are provided in `git-hooks/` and should be installed locally.

---

## Notes

- All tool/skill executions are containerized; if Docker is unavailable, tool execution fails.
- Keep production-sensitive values (tokens, phone numbers, live infra details) out of commits.

## License

MIT — see `LICENSE`.
