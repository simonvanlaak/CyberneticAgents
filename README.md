# CyberneticAgents

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Architecture: VSM](https://img.shields.io/badge/architecture-viable%20systems%20model-6f42c1)](docs/discoverability.md)

CyberneticAgents is an **agentic multi-agent runtime** grounded in **cybernetics**, **Stafford Beer**'s **Viable Systems Model (VSM)**, and practical **systems theory**.

Built with **AutoGen Core** and **Casbin RBAC**, it models Systems 1/3/4/5 as cooperating agents and enforces role boundaries for cross-agent actions.

## What it includes

- Multi-agent runtime (AutoGen Core + AgentChat)
- VSM roles implemented: System 1, 3, 4, 5
- Casbin RBAC authorization for delegation/tool actions
- CLI-first workflows, optional Telegram interaction
- Label-driven GitHub issue-stage workflow for implementation automation
- Taiga-backed operational task board flow (MVP migration path)

---

## Quick start

Docs entry points:
- `docs/README.md` (entrypoint)
- `docs/discoverability.md` (keywords + architecture context)

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

- `OPENAI_API_KEY` (required by default)
- `BRAVE_API_KEY` (required for web search)
- `GROQ_API_KEY` (only if `LLM_PROVIDER=groq`)
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

## Unified Docker stack (Taiga + CyberneticAgents)

Bring up the full MVP stack from repo root:

```bash
docker compose up -d --build
```

Quick health checks:

```bash
docker compose ps
curl -fsS "http://127.0.0.1:${TAIGA_PUBLIC_PORT:-9000}/api/v1/"
docker compose logs --tail=100 taiga-back
docker compose logs --tail=100 cyberagent
```

Detailed bootstrap/runbook:

- `docs/technical/taiga_mvp_bootstrap.md`

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

- `stage:backlog` (parked; not in automation queue)
- `stage:queued` (automation triage queue)
- `stage:needs-clarification`
- `stage:ready-to-implement`
- `stage:in-progress`
- `stage:in-review`
- `stage:blocked`

### Canonical automation tooling

- `https://github.com/simonvanlaak/GhIssueWorkflow`
  - standalone stage-label queue engine (multi-repo)
- `./scripts/quality_gate.sh`
  - required quality gate before review/push in this repo

**No GitHub Projects v2 queue is used for active automation flow.**

### Task board of record

- The operational task board is **Taiga UI**.
- Open it with `cyberagent kanban`.
- `cyberagent dashboard` remains a read-only operational view (teams/inbox/memory), not a task board.

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
│   ├── agents/        # legacy compatibility namespace
│   ├── rbac/          # legacy compatibility namespace
│   ├── tools/         # legacy compatibility namespace
│   └── registry.py    # legacy compatibility entrypoint
└── tests/
```

---

## Contributing

We’re very much looking forward to **feedback and suggestions**.

Please **open a GitHub Issue** as a **“Prompt Request”** and describe your suggested change in detail.

- **Do not create Pull Requests.**
- Instead, explain what you’d change (and why) in an issue — if it fits the overall concept and vision, I’ll implement it.

See: [CONTRIBUTING.md](CONTRIBUTING.md)

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
