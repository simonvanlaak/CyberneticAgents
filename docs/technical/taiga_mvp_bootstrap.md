# Taiga MVP bootstrap (CyberneticAgents)

> **DEPRECATED — LEGACY**: Taiga has been replaced by Planka as the operational task board. This document is kept for historical reference only. See `docs/technical/planka_compose_ops_runbook_2026-02-16.md` for the current runbook.


Ticket: #119

Goal: run a unified self-hosted stack (Taiga + CyberneticAgents) with a single root `docker-compose.yml` and one `.env` contract.

## Bring up unified stack (Docker)

```bash
cd /root/.openclaw/workspace/CyberneticAgents
cp .env.example .env
# Edit .env (secrets + required placeholders)

docker compose up -d --build
```

Open Taiga:

- `http://<host>:${TAIGA_PUBLIC_PORT:-9000}`

## Health checks

```bash
docker compose ps
curl -fsS "http://127.0.0.1:${TAIGA_PUBLIC_PORT:-9000}/api/v1/"
docker compose logs --tail=100 taiga-back
docker compose logs --tail=100 cyberagent
```

## MVP bootstrap checklist

### 1) Create project

- Name: `CyberneticAgents`
- Slug: `cyberneticagents`

### 2) Create bot users

Create two users:

- `taiga-admin@local` (admin/bootstrap)
- `taiga-bot@local` (runtime / least privilege)

Store credentials in 1Password.

### 3) Task statuses (match CyberneticAgents Status enum)

Ensure Taiga **Task** statuses match these canonical values (order can vary):

- `pending`
- `in_progress`
- `completed`
- `blocked`
- `approved`
- `rejected`
- `canceled`

### 4) Custom field

Add a **Task custom field**:

- `cyber_initiative_id` (string/int)

This links a Taiga task back to the current CA initiative.

## Notes

- SMTP/email is intentionally skipped for MVP.
- #114 PoC bridge implementation is documented in `docs/technical/taiga_adapter_poc.md`.
- Runtime worker-loop hardening is tracked separately in #124.
