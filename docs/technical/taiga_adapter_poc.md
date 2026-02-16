# Taiga adapter PoC runbook

Ticket: #114

This PoC validates the thin Taiga bridge loop for CyberneticAgents:

1. Pull one assigned Taiga task from `pending`.
2. Append an automation result comment.
3. Transition the task status to `completed`.

## Scope boundary

- This document covers **adapter/workflow PoC code only**.
- Taiga self-host/bootstrap infra is documented separately in:
  - `docs/technical/taiga_mvp_bootstrap.md`
  - `docker-compose.yml`

## Required environment

Set these variables (e.g., in `.env`):

```bash
TAIGA_BASE_URL=http://localhost:9000
TAIGA_TOKEN=<taiga-api-token>
```

Optional overrides:

```bash
TAIGA_PROJECT_SLUG=cyberneticagents
TAIGA_ASSIGNEE=taiga-bot
TAIGA_SOURCE_STATUS=pending
TAIGA_TARGET_STATUS=completed
TAIGA_RESULT_COMMENT="Automated result: completed by CyberneticAgents Taiga PoC adapter."
```

## Run once

```bash
cd /root/.openclaw/workspace/CyberneticAgents
python -m scripts.taiga_poc_bridge
```

Expected output:

- If a matching task exists:
  - `Processed Taiga task #<ref> (id=<id>) and moved it to status 'completed'.`
- If no matching task exists:
  - `No matching Taiga task found for the configured assignment/status.`

## Test coverage

- `tests/cyberagent/test_taiga_adapter.py`
- `tests/scripts/test_taiga_poc_bridge.py`

These tests assert:

- Assigned-task polling filter contract.
- Result comment + status patch payload.
- Error behavior for missing target statuses.
- One-shot bridge behavior for a single task cycle.
