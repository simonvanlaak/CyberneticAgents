# OpenProject Integration Evaluation (CyberneticAgents)

Date: 2026-02-15  
Issue: #91

## 1) Executive recommendation

**Recommendation: Adopt OpenProject later (phased), not immediately.**

Why (weighted by operational overhead):
1. OpenProject can cover our required MVP workflow (board + assignment + comments + status transitions), but self-hosting adds a second production system to run and secure.
2. The agent-per-user model is feasible through API/user/membership endpoints, but provisioning lifecycle and permission hardening are non-trivial.
3. We can de-risk by running OpenProject in parallel with Notion first, then switching once reliability and migration quality are proven.

Decision summary:
- **Now:** prepare and run a small parallel MVP.
- **Later (after validation):** move primary task operations to OpenProject.
- **Not recommended:** immediate hard cutover from Notion without coexistence window.

---

## 2) Product/technical fit vs our needs

## Core concepts that map well
- **Work packages** = task records we can assign, track, and comment on.
- **Boards** = kanban-style visual planning over work packages.
- **Users/roles/memberships** = foundation for “real user per agent”.
- **REST API v3 (HAL+JSON)** = full server-side integration surface.

## Important feature caveat
- OpenProject docs state **Basic board** is available in Community edition.
- **Action boards** (status/assignee/version boards with automatic attribute updates when dragging cards) are Enterprise add-ons.

Implication:
- If we require drag-and-drop to directly update status/assignee, confirm Enterprise availability/budget.
- If Community-only, we should rely on work package detail actions/API updates for status/assignee, and use basic boards for visibility.

---

## 3) API feasibility for required operations

## Required operations and endpoint mapping

1. **List/query work items**
   - `GET /api/v3/workspaces/{id}/work_packages`
   - Supports paging, filters, sorting, grouping.

2. **Claim/assign work item**
   - Discover candidates: `GET /api/v3/workspaces/{id}/available_assignees`
   - Update assignee: `PATCH /api/v3/work_packages/{id}` (`_links.assignee`, with `lockVersion`).

3. **Update status**
   - `PATCH /api/v3/work_packages/{id}` (`_links.status`, with `lockVersion`).

4. **Append structured results/comments**
   - `POST /api/v3/work_packages/{id}/activities` (comment/journal entry).

5. **Create/manage users for agents**
   - `POST /api/v3/users` (create user; admin/manage_user permissions needed).
   - `POST /api/v3/memberships` (assign user to project/workspace roles).

6. **Read complete task timeline/history**
   - `GET /api/v3/work_packages/{id}/activities`.

## Practical integration notes
- OpenProject API is hypermedia/HAL; action links can be permission-sensitive.
- Work package updates require optimistic locking (`lockVersion`).
- Deprecated project-scoped endpoints exist in docs; prefer workspace-scoped endpoints where documented.

Verdict: **API coverage is sufficient for MVP.**

---

## 4) Auth model options (server-side)

OpenProject supports:
1. API token (Bearer or Basic with `apikey`).
2. OAuth2 (authorization code, PKCE, client credentials).

## Recommended for MVP
- **Primary:** API token per automation identity (simpler ops, faster bring-up).
- **Optional later:** OAuth2 client credentials when centralizing token lifecycle and policy.

Why:
- Minimizes moving parts in early phase.
- Works well for background workers and deterministic API calls.

Security baseline:
- Keep tokens in secret manager (1Password/secure env injection).
- Use least privilege roles for agent users.
- Rotate/revoke tokens as part of offboarding or compromise response.

---

## 5) Eventing: webhook vs polling

OpenProject provides webhooks configurable for events including work packages and comments.

## Recommended ingestion pattern
1. **Primary trigger:** webhooks for near-real-time updates.
2. **Safety net:** periodic poll/reconciliation (e.g., every 1–5 min) for missed events/network failures.
3. Validate webhook signature secret.
4. Ensure idempotent event handling by storing last processed event identity/timestamp per workspace.

Verdict: **Webhook + reconciliation polling** is the most robust option.

---

## 6) Self-hosting effort (Docker baseline)

## What docs indicate
- Docker deployment is the recommended path.
- Baseline server guidance (up to ~200 users): roughly **4 CPU, 4 GB RAM, 20 GB disk**.
- PostgreSQL 16+ officially supported.
- Backups/upgrades are documented in Docker Compose flow.

## Operational overhead to account for
1. Service lifecycle: deployment, upgrades, rollback windows.
2. Data safety: DB + attachment backups and restore drills.
3. Security: TLS/reverse proxy, network exposure, token management.
4. Monitoring: availability, queue depth, DB health, API latency/errors.

For thesis/hackathon scale, this is feasible but not “zero-maintenance”.

---

## 7) Migration + coexistence plan (Notion -> OpenProject)

## Coexistence is viable and recommended
Run OpenProject in parallel first.

## Suggested mapping
- Notion task -> OpenProject work package
- Notion assignee/agent -> OpenProject user (agent account)
- Notion status -> OpenProject status
- Notion comments/log -> work package activities/comments
- Notion IDs -> custom field or external reference link in OpenProject

## Rollout strategy
1. **Read-only mirror phase**: ingest OpenProject changes, no ownership switch.
2. **Dual-write phase**: write from worker to both systems for selected flows.
3. **Primary switch**: OpenProject becomes source of truth for selected projects.
4. **Decommission phase**: retire overlapping Notion automation paths.

---

## 8) Agent-user model

Target: one real OpenProject user per agent role.

## Proposed model
1. Provision agent user (API/admin flow).
2. Assign role(s) via membership per workspace.
3. Store mapping: `agent_id -> openproject_user_id` in CyberneticAgents config/store.
4. Worker selects acting identity and executes assignment/comment/status updates with explicit audit metadata.

Notes:
- Keep role templates minimal and principle-of-least-privilege.
- Define naming convention early (e.g., `agent-sys3-control`, `agent-sys1-ops-<name>`).

---

## 9) Concrete MVP plan (Telegram-first acceptable)

## MVP scope
- Single OpenProject workspace for CyberneticAgents tasks.
- API integration for:
  - query candidate tasks
  - claim/assign
  - status update
  - comment results back
- Optional Telegram notifications for assignment/result summaries.
- Agent-user provisioning for a small fixed set of agents (not dynamic autoscaling yet).

## Required infra steps
1. Deploy OpenProject via Docker Compose on a dedicated host (or isolated VM).
2. Configure TLS/reverse proxy and restricted ingress.
3. Create admin + role templates.
4. Provision initial agent users and memberships.
5. Configure secrets and webhook endpoint.

## API endpoints needed in implementation
- `GET /api/v3/workspaces/{id}/work_packages`
- `GET /api/v3/workspaces/{id}/available_assignees`
- `PATCH /api/v3/work_packages/{id}`
- `POST /api/v3/work_packages/{id}/activities`
- `GET /api/v3/work_packages/{id}/activities`
- `POST /api/v3/users`
- `POST /api/v3/memberships`

## Effort estimate
- **MVP integration only:** **M (5–8 days)**
  - API client + mapping + error handling + retries + lockVersion handling
  - webhook receiver + reconciliation poller
  - agent-user provisioning scripts
- **Production hardening:** **M/L (+4–8 days)**
  - monitoring, backup/restore drill, runbooks, security hardening, migration cutover checks

---

## 10) Go/No-Go criteria for starting implementation

Proceed with implementation when these are confirmed:
1. Community vs Enterprise decision (Action boards requirement).
2. Hosting target and owner for OpenProject operations.
3. Accepted coexistence window and migration checkpoints.
4. Initial agent roster and role matrix.

If confirmed, create follow-up implementation issues:
1. OpenProject infrastructure bootstrap.
2. API client + domain mapping layer.
3. Webhook + reconciliation worker.
4. Agent-user provisioning + membership management.
5. Dual-write migration adapter + validation report.

---

## Reference sources
- API intro/auth: https://www.openproject.org/docs/api/introduction/
- Work package API: https://www.openproject.org/docs/api/endpoints/work-packages/
- API/webhooks admin: https://www.openproject.org/docs/system-admin-guide/api-and-webhooks/
- OAuth apps: https://www.openproject.org/docs/system-admin-guide/authentication/oauth-applications/
- Docker Compose install: https://www.openproject.org/docs/installation-and-operations/installation/docker-compose/
- System requirements: https://www.openproject.org/docs/installation-and-operations/system-requirements/
- Agile boards: https://www.openproject.org/docs/user-guide/agile-boards/
- Roles/permissions: https://www.openproject.org/docs/system-admin-guide/users-permissions/roles-permissions/
- API spec paths (raw): https://raw.githubusercontent.com/opf/openproject/dev/docs/api/apiv3/openapi-spec.yml
