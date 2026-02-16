# Taiga MVP bootstrap (CyberneticAgents)

Ticket: #120

Goal: run a self-hosted Taiga instance (Docker) and bootstrap a single project used as the MVP task backend.

## Bring up Taiga (Docker)

```bash
cd /root/.openclaw/workspace/CyberneticAgents
cp .env.taiga.example .env.taiga
# Edit .env.taiga (secrets, domain)

docker compose --env-file .env.taiga -f docker-compose.taiga.yml up -d
```

Open Taiga:

- `http://<host>:9000` (or whatever `TAIGA_PUBLIC_PORT` is)

## MVP bootstrap checklist

### 1) Create project

- Name: `CyberneticAgents`
- Slug: `cyberneticagents`

### 2) Create bot users

Create two users:

- `taiga-admin@local` (admin/bootstrap)
- `taiga-bot@local` (runtime / least privilege)

Store passwords in 1Password.

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
- #114 PoC bridge implementation is documented in `docs/technical/taiga_adapter_poc.md` and runnable via `python -m scripts.taiga_poc_bridge`.
