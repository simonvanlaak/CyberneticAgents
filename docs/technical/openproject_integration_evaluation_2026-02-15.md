# OpenProject Integration Evaluation (CyberneticAgents)

Date: 2026-02-15  
Issue: #91

## 1) Executive recommendation

**Updated recommendation:** keep **OpenProject as a phased option** (not immediate cutover), and run one short comparison spike with **Taiga** before committing.

Reasoning (weighted by **operational overhead** first):
1. Current in-repo board is lightweight but incomplete for the desired workflow: the Streamlit dashboard is read-only and there is no implemented user-facing ticket assignment/move flow yet.
2. OpenProject has strong API/workflow coverage for our target model (assignment, statuses, comments, memberships, agent users), but adds meaningful hosting/ops load.
3. Among self-hosted OSS alternatives reviewed, Taiga is the closest functional challenger; Plane is promising but similarly multi-service, and Wekan’s REST API documentation explicitly notes incomplete coverage.

Decision summary:
- **Now:** do not hard-cutover; keep current Streamlit+SQLite baseline as source of truth.
- **Next:** run a small OpenProject vs Taiga spike focused on worker API fit + ops friction.
- **Later:** choose one external system and migrate in phases.

---

## 2) Current baseline in this repo (correction)

The prior draft incorrectly referenced Notion as the current task board for this project.

For **CyberneticAgents**, the baseline is:
- Streamlit dashboard UI over SQLite task data.
- Dashboard is explicitly read-only for Kanban/team views.
- No existing implementation for end users to directly assign or move tickets through that UI.

Implication: any external PM integration (OpenProject/Taiga/Plane/...) must include:
1. data mapping from SQLite task records,
2. assignment/status synchronization,
3. identity mapping for agent users,
4. migration/coexistence safety.

---

## 3) OpenProject fit against required capabilities

OpenProject maps well to target requirements:
- **Work packages** for task records.
- **Boards** for Kanban visualization.
- **Users/roles/memberships** for agent-per-user model.
- **REST API v3** for automation.
- **Webhooks** + polling fallback for reliable event ingestion.

Key caveat:
- Community edition provides basic boards; advanced board automation features may require enterprise options.

Bottom line: OpenProject is functionally strong, but not low-overhead.

---

## 4) Self-hosted OSS alternatives (requested scope)

Compared alternatives:
- **Plane**
- **Taiga**
- **Wekan**

### 4.1 Snapshot matrix

| Option | Operational overhead (primary) | API/worker fit (assign/status/comment/user) | Eventing | Migration complexity from current baseline | Notes |
|---|---|---|---|---|---|
| OpenProject | High | High | Webhooks + poll fallback | Medium/High | Most complete governance model; heaviest ops footprint |
| Taiga | Medium/High | High | Webhooks (HMAC-signed) | Medium | Strong challenger for our use case |
| Plane | Medium/High | Medium/High | Webhooks + signatures | Medium | Modern API/webhooks; still similar infra class |
| Wekan | Low/Medium | Low/Medium | Limited in reviewed docs | Medium | REST docs explicitly say API is not complete |

### 4.2 Practical takeaways

- **Taiga** is the closest “could match criteria with somewhat less overhead” candidate to validate in a short spike.
- **Plane** is promising, but not clearly lower effort operationally for our environment.
- **Wekan** is attractive for simple Kanban, but current REST API maturity signal is weaker for our automation-heavy workflow.

---

## 5) OpenProject API feasibility (required operations)

Required operations and endpoint families:
1. **List/query work items**: work package listing/filtering.
2. **Claim/assign**: assignee updates via work package patch operations.
3. **Update status**: status links/patch operations.
4. **Append structured comments/results**: activity/journal endpoints.
5. **Create/link users for agents**: user + membership endpoints.
6. **Read timeline/history**: work package activity history.

Integration notes:
- API is HAL-based; available links/actions can be permission-sensitive.
- Update flows use optimistic locking (`lockVersion`).

Verdict: coverage is sufficient for MVP worker automation.

---

## 6) Authentication model

OpenProject supports:
- API tokens (Bearer or Basic `apikey` pattern)
- OAuth2 application flows

MVP recommendation:
- Start with API tokens per automation identity.
- Move to OAuth2 app model only if/when central token lifecycle and policy demands it.

Security baseline:
- Secret-manager backed storage,
- least-privilege roles,
- documented rotation/revocation.

---

## 7) Eventing approach

Recommended pattern (OpenProject and similarly for Taiga/Plane where applicable):
1. webhook ingestion for low latency,
2. periodic reconciliation poll for missed events,
3. idempotent processing keyed by event identifiers,
4. signature verification on inbound callbacks.

---

## 8) Hosting effort (OpenProject docker baseline)

OpenProject docs indicate a non-trivial but manageable ops profile:
- Docker-oriented deployment,
- PostgreSQL dependency,
- explicit backup/upgrade expectations,
- baseline sizing around small-team server resources.

For thesis/hackathon scale: feasible, but not “set-and-forget”.

---

## 9) Migration + coexistence plan (current Streamlit+SQLite -> external PM)

### Suggested mapping
- SQLite `tasks` row -> external task/work package/card
- internal `tasks.assignee` -> external user identity (agent user)
- internal status -> external workflow status
- internal result/reasoning/execution log -> external comments/activities
- internal task id -> external reference field

### Rollout
1. **Mirror-read phase**: ingest external updates, no ownership switch.
2. **Dual-write phase**: selected flows write both systems.
3. **Primary switch**: external system becomes source of truth.
4. **Decommission**: retire temporary sync paths.

---

## 10) Agent-user model

Target remains: **one real external account per agent role**.

Implementation shape:
1. provision user account,
2. grant scoped membership/role,
3. persist `agent_id -> external_user_id` mapping,
4. stamp audit metadata on all worker actions.

---

## 11) MVP implementation scope (if OpenProject chosen)

- Single workspace/project for CyberneticAgents tasks.
- Worker features:
  - pull candidate tasks,
  - claim/assign,
  - update status,
  - append structured result comments.
- Initial fixed roster of agent users.
- Optional Telegram summary notifications.

Estimated effort:
- Integration MVP: **M (~5–8 days)**
- Hardening + migration controls: **M/L (+4–8 days)**

---

## 12) Go/No-Go criteria

Proceed when all are explicit:
1. OpenProject vs Taiga final selection after spike.
2. Hosting owner + backup/upgrade responsibility.
3. Accepted coexistence window + migration checkpoints.
4. Initial agent roster + role matrix.

If approved, create follow-up tickets for:
1. infra bootstrap,
2. API client + domain mapping,
3. webhook + reconciliation worker,
4. agent-user provisioning,
5. migration adapter + validation report.

---

## Reference sources

### OpenProject
- API intro/auth: https://www.openproject.org/docs/api/introduction/
- Work package API: https://www.openproject.org/docs/api/endpoints/work-packages/
- API/webhooks admin: https://www.openproject.org/docs/system-admin-guide/api-and-webhooks/
- OAuth apps: https://www.openproject.org/docs/system-admin-guide/authentication/oauth-applications/
- Docker install: https://www.openproject.org/docs/installation-and-operations/installation/docker-compose/
- System requirements: https://www.openproject.org/docs/installation-and-operations/system-requirements/
- Boards: https://www.openproject.org/docs/user-guide/agile-boards/
- Roles/permissions: https://www.openproject.org/docs/system-admin-guide/users-permissions/roles-permissions/

### Plane
- Self-hosting overview: https://developers.plane.so/self-hosting/overview
- API intro/auth (X-API-Key): https://developers.plane.so/api-reference/introduction
- Webhooks: https://developers.plane.so/dev-tools/intro-webhooks

### Taiga
- API docs: https://docs.taiga.io/api.html
- API auth/general notes (Bearer/Application tokens, OCC): https://raw.githubusercontent.com/taigaio/taiga-doc/main/api/general-notes.adoc
- Webhooks config: https://docs.taiga.io/webhooks-configuration.html
- Webhooks technical details: https://raw.githubusercontent.com/taigaio/taiga-doc/main/webhooks.adoc
- Docker deployment repo: https://github.com/taigaio/taiga-docker

### Wekan
- REST API wiki (includes “REST API is not complete yet” note): https://raw.githubusercontent.com/wiki/wekan/wekan/REST-API.md
- Project/deployment docs entry points: https://github.com/wekan/wekan

### Current CyberneticAgents baseline
- Dashboard feature docs (read-only): `docs/features/dashboard.md`
- Streamlit dashboard: `src/cyberagent/ui/dashboard.py`
- SQLite Kanban data loader: `src/cyberagent/ui/kanban_data.py`

---

## 13) Spike addendum (Issue #113, desk analysis refresh)

This addendum captures the time-boxed OpenProject vs Taiga review requested in #113, using desk analysis only (docs/API/ops), and keeping the current Streamlit+SQLite board as the baseline comparator.

### 13.1 API surface comparison for our automation flows

| Required automation capability | OpenProject | Taiga | Current Streamlit+SQLite board |
|---|---|---|---|
| List/query tasks | Mature Work Package query/filter API (REST v3) | Mature issues/user stories/tasks API | Internal SQLite reads already available |
| Assignment/claim | Assignee updates supported; permissioned and lock-version aware | Assignment fields supported through API; concurrency-aware updates | No end-user claim flow in current UI |
| Status transitions | Workflow/status updates via API actions | Workflow/status updates via API | Status storage exists, but no full Kanban interaction UX |
| Append comments/results | Journal/activity comments supported | Comment endpoints supported | Internal logs/comments possible but not integrated in a full PM workflow |
| Users + role mapping for agent identities | Strong users/roles/memberships model | Users/projects/roles supported; leaner model | No external identity model; custom mapping required |

**Readout:** both OpenProject and Taiga cover required worker operations. OpenProject is more explicit/enterprise-shaped around permissions and governance; Taiga is typically simpler to approach.

### 13.2 Authentication + server-side automation ease

- **OpenProject:** API token and OAuth2 options are clearly documented; good fit for long-lived backend automation identities with explicit role control.
- **Taiga:** bearer token model is straightforward and automation-friendly; lower conceptual overhead to get started.
- **Current board:** no external auth boundary, but adding robust multi-user/agent auth remains our burden.

**Readout:** Taiga is slightly easier for quick automation startup; OpenProject is stronger if we anticipate stricter governance/audit controls.

### 13.3 Hosting / operations overhead comparison

- **OpenProject:** heaviest stack in this comparison (PostgreSQL + app services + upgrade/backup discipline).
- **Taiga:** still multi-service and non-trivial, but generally lighter to operate than OpenProject.
- **Current board:** lowest immediate infra overhead, but feature development and maintenance cost shifts to us.

### 13.4 Recommendation (OpenProject vs Taiga vs stay current)

For the immediate next decision window, the best recommendation is:

1. **Stay on the current board temporarily** while Simon performs UI review of OpenProject and Taiga.
2. Keep **Taiga** as the likely lower-friction migration candidate if we optimize for speed/ops simplicity.
3. Keep **OpenProject** as the likely better fit if governance depth (roles/permissions/auditability) is prioritized over runtime simplicity.

This is still a recommendation (not a tie): **defer cutover now, choose after UI review, with Taiga favored for lighter operations unless governance requirements dominate.**

### 13.5 Minimal MVP plan (for whichever external tool is selected)

1. Stand up one project/workspace and one service account per agent role (or a bootstrap subset).
2. Implement the four core worker actions only:
   - pull/list candidate work
   - claim/assign
   - move status
   - append structured result comment
3. Run dual-write/verification against SQLite task records for a limited pilot window.
4. Produce a short validation report (API reliability, operator friction, migration risk) before any full cutover.

Per issue instruction, **no follow-up implementation tickets are created yet**; selection happens after owner review.
