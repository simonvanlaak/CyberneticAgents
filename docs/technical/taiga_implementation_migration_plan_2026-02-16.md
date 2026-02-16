# Taiga implementation + migration plan (MVP cutover)

Ticket: #115

## Purpose
Define an actionable plan to make **Taiga the task system-of-record** for CyberneticAgents and remove the in-repo Streamlit+SQLite task board paths.

This plan follows the resolved constraints in #115:
- GitHub issue stage labels remain implementation workflow only.
- Taiga becomes CyberneticAgents task workflow source-of-truth.
- MVP is a clean cutover (no dual-write, no rollback track for MVP).
- Keep auth/user model simple.

## 1) Target workflow definition

### Scope boundary
- **GitHub labels (`stage:*`)**: implementation queue for repo work.
- **Taiga**: runtime task queue used by CyberneticAgents task execution loops.

### Concept mapping

| Current / desired capability | Current source | Taiga target |
|---|---|---|
| Task backlog and active work | SQLite task tables + Streamlit board | Taiga Project + Tasks |
| Task status lifecycle | Local status enum in app/db | Taiga Task Statuses (`pending`, `in_progress`, `completed`, `blocked`, `approved`, `rejected`, `canceled`) |
| Assignment / claiming | Local assignee fields | Taiga task assignee + API claim/update |
| Result capture | Local task.result / case data | Taiga task comment + final status transition |
| Human-facing board UI | Streamlit dashboard | Taiga web UI |

## 2) Infrastructure plan (self-hosted Taiga + CA)

### Topology
Target stack (single compose deployment; tracked in #119):
- Taiga services (front/back/events and required dependencies like postgres/rabbitmq/redis)
- CyberneticAgents service container(s)

### Environment and secrets
- Use a single `.env` contract for MVP (per #119 clarification).
- Keep secrets out of git; keep only `.env.example` placeholders.

### Persistence and backup
Minimum persisted data:
- Taiga Postgres volume
- Taiga media/static volume(s)

Backup policy (MVP pragmatic baseline):
- Daily Postgres dump (`pg_dump`) + retained rotation (e.g., last 7 daily snapshots)
- Periodic volume snapshot for media
- Document restore command path in ops runbook ticket (queued in this plan)

### Operations
- Health checks for Taiga API reachability and CA service liveness
- Explicit compose restart procedures
- Log locations and quick diagnosis commands in docs

## 3) Integration design

Build on the existing PoC adapter in `src/cyberagent/integrations/taiga/adapter.py`.

### Required Taiga API operations
- List assigned tasks by project + status (`GET /api/v1/tasks` with filters)
- Read task details/version (`GET /api/v1/tasks/{id}`)
- Resolve available statuses (`GET /api/v1/task-statuses?project=<id>`)
- Post result + transition status (`PATCH /api/v1/tasks/{id}` with `comment`, `status`, `version`)

### Runtime contract
1. Poll Taiga for candidate assigned `pending` tasks.
2. Claim/start task by transition to `in_progress`.
3. Execute work loop.
4. Write result comment and transition to terminal status (`completed` / `blocked` / etc.).

### Auth model (MVP)
Simple two-user baseline:
- `taiga-admin` for setup/bootstrap only
- `taiga-bot` for runtime automation

## 4) Migration strategy (clean cutover)

### Phase A — prep and infra
- Finish compose stack and docs (#119).
- Validate Taiga project + status model alignment.

### Phase B — runtime readiness
- Promote adapter from PoC to operational worker loop.
- Add robustness for status transitions and failure visibility.

### Phase C — cutover and legacy removal
- Stop using Streamlit+SQLite task board paths for task queueing.
- Remove/disable dashboard task board entrypoints and related docs/tests as applicable.
- Switch operations to Taiga UI for work tracking.

### MVP rollback posture
- No rollback implementation track for MVP.
- If severe issues appear, fix-forward on Taiga integration path.

## 5) Sequenced implementation ticket breakdown

Existing relevant tickets:
1. **#119** — Dockerized unified compose stack (Taiga + CyberneticAgents) — **M**
2. **#114** — Taiga adapter PoC baseline (already implemented/in review) — **S**

Missing follow-up tickets created from this plan:
3. **#124** — productionize Taiga worker loop + status transition semantics — **M**
   - Depends on #114
4. **#125** — remove Streamlit+SQLite task board paths and route operators to Taiga UI — **M**
   - Depends on #119 and #124
5. **#126** — Taiga ops runbook (backup/restore + healthchecks) for compose deployment — **S**
   - Depends on #119

## 6) Acceptance checklist for this planning ticket
- [x] Actionable technical plan doc under `docs/technical/`
- [x] Sequenced implementation ticket set with dependencies and S/M/L sizing
- [x] Explicit migration/cutover strategy aligned to MVP constraints
- [x] Separation of concerns: GitHub labels for implementation; Taiga for CA task runtime
