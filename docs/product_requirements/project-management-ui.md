# Project Management UI: Read-Only Kanban Scope

## Goal
Deliver a very quick, local, read-only web UI for task visibility:
- Kanban board by task status.
- Assignee visibility on each card.
- No editing in phase 1.

## Current Implementation (Verified in Code)

### Data model and orchestration
- Hierarchy is implemented in SQLite/SQLAlchemy as:
  - `Purpose -> Strategy -> Initiative -> Task`
  - Files: `src/cyberagent/db/models/purpose.py`, `src/cyberagent/db/models/strategy.py`, `src/cyberagent/db/models/initiative.py`, `src/cyberagent/db/models/task.py`
- Procedure templates and executions are separate entities:
  - `Procedure`, `ProcedureTask`, `ProcedureRun`
  - Files: `src/cyberagent/db/models/procedure.py`, `src/cyberagent/db/models/procedure_task.py`, `src/cyberagent/db/models/procedure_run.py`
- Status flow currently includes `pending`, `in_progress`, `completed`, `approved`, `rejected`:
  - File: `src/enums.py`

### Human-facing UI today
- Current user-facing project management view is CLI only (`cyberagent status`), not web UI:
  - File: `src/cyberagent/cli/status.py`

## Agreed Phase 1 Scope
- Technology: Streamlit (self-built local UI).
- Mode: read-only.
- Views:
  - Kanban columns for `pending`, `in_progress`, `completed`, `approved`, `rejected`.
  - Optional table view for scanning/searching.
- Filters:
  - team, strategy, initiative, assignee.
- Refresh:
  - manual refresh + optional periodic auto-refresh.
- Explicitly out of scope:
  - status/assignee/content edits from UI,
  - authentication/RBAC for UI users,
  - replacing current runtime/agent orchestration.

## Effort Estimate (Agreed Scope)
- MVP read-only Streamlit Kanban: ~1-3 days
- Hardened local version (tests, docs, perf tuning): ~3-5 days
- Reference technical plan: `docs/technical/streamlit_readonly_kanban_plan.md`

## Why This Scope
- Fastest path to immediate visibility for humans.
- Minimal risk because there are no UI writes.
- Avoids integration overhead with external PM tools in phase 1.

## Phase 2 Candidates (Deferred)
- Add editing capabilities (status changes, assignee updates).
- Add auth + RBAC-aware visibility.
- Evaluate external PM tools (OpenProject, WeKan, Vikunja, etc.) if richer planning workflows are required.

## OpenProject Capabilities (Official Docs)

- OpenProject provides a web UI centered on Work Packages (tasks/issues) with hierarchy and relations:
  - Work package relations/hierarchy docs:  
    https://www.openproject.org/docs/user-guide/work-packages/work-package-relations-hierarchies
- Gantt module supports timeline planning, dependencies, and parent/child hierarchy:
  - https://www.openproject.org/docs/user-guide/gantt-chart
- Boards (Kanban) are available; basic boards are in Community edition:
  - https://www.openproject.org/docs/getting-started/boards-introduction
- API v3 is available with OpenAPI spec (`/api/v3/spec.json`) for integration:
  - https://www.openproject.org/docs/api/introduction
  - https://www.openproject.org/docs/api/endpoints/work-packages
- Webhooks are available for project/work package events:
  - https://www.openproject.org/docs/system-admin-guide/api-and-webhooks
- Recommended deployment is Docker/Docker Compose:
  - https://www.openproject.org/docs/installation-and-operations/installation
  - https://www.openproject.org/docs/installation-and-operations/installation/docker

## Fit vs Current Model

### Strong fit
- `Task` maps well to OpenProject `WorkPackage`.
- `Initiative` can map to parent work packages (epic/feature style) with child tasks.
- Existing task dependencies can map to work package relations.
- CLI-only visibility gap is solved immediately by OpenProject UI (table/board/gantt).

### Partial / custom mapping needed
- `Purpose` and `Strategy` are not first-class OpenProject entities.
  - Need mapping to project-level metadata, parent work packages, or custom fields.
- `Procedure` / `ProcedureRun` semantics (versioned SOP execution) are domain-specific.
  - Need custom representation in OpenProject (labels/custom fields/linked parent items).
- Current status model (`approved` / `rejected`) must be mapped to OpenProject status workflows.

## Migration Options

### Option A: OpenProject as UI layer, CyberneticAgents remains system of record (recommended first step)
- One-way sync from CyberneticAgents DB to OpenProject.
- Humans manage views in OpenProject; agent logic still uses internal DB.
- Lowest risk for initial adoption.

### Option B: Bi-directional sync
- User edits in OpenProject must sync back to CyberneticAgents DB.
- Requires webhook ingestion, conflict handling, idempotency, and ownership rules.
- Higher complexity and regression risk.

## Effort Estimate (UI Migration to OpenProject)

Assumptions:
- 1 experienced engineer familiar with current codebase.
- No full replacement of agent orchestration logic.
- Start with Option A, then evaluate Option B.

### Option A (one-way sync, OpenProject for human UI): ~3-5 weeks
1. Environment + OpenProject provisioning (Docker Compose, auth, project setup): 2-4 days
2. Schema mapping design (`Purpose/Strategy/Initiative/Task` -> OpenProject model): 2-3 days
3. Initial sync job + incremental updates via API v3: 6-9 days
4. Status/workflow mapping and validation: 2-3 days
5. UI conventions (saved views/boards/gantt queries) + docs: 2-4 days
6. Testing/observability/hardening: 3-5 days

### Option B (bi-directional sync): +4-8 weeks additional
1. Webhook receiver + signature verification + replay safety: 4-7 days
2. Change ownership rules (human vs agent), conflict resolution, merge semantics: 7-12 days
3. Back-sync into local models with audit trail and retries: 7-10 days
4. End-to-end reliability testing and rollback plans: 5-10 days

## Recommendation
- Do not execute OpenProject migration in phase 1.
- Execute Streamlit read-only Kanban first.
- Revisit OpenProject and other integrations only after phase 1 usage validates additional requirements.

## Lower-Effort UI Alternatives

If the immediate goal is a low-effort board for task status movement + assignee visibility, these alternatives are likely cheaper than OpenProject integration.

### Estimated effort vs OpenProject
- OpenProject Option A (reference): ~3-5 weeks
- Custom internal Kanban MVP (reference): ~2-4 weeks
- WeKan integration: ~1-2 weeks
- Planka integration: ~1-2.5 weeks
- Vikunja integration: ~1.5-3 weeks
- NocoDB integration: ~1-3 weeks
- Taiga integration: ~2-4 weeks
- Plane CE integration: ~2-4 weeks

### Option notes
- WeKan:
  - Strength: Kanban-first, self-hosted, fast to stand up.
  - Tradeoff: More limited PM depth than OpenProject.
- Planka:
  - Strength: Very simple Trello-style board UX.
  - Tradeoff: Fair-code/source-available licensing; verify policy fit.
- Vikunja:
  - Strength: Kanban + list + timeline/gantt-style planning in one tool.
  - Tradeoff: Slightly more integration surface than board-only tools.
- NocoDB:
  - Strength: Fastest path for CRUD/table-backed UI with kanban view.
  - Tradeoff: Data modeling and workflow semantics may need adaptation.
- Taiga / Plane CE:
  - Strength: Richer PM features than pure Kanban tools.
  - Tradeoff: More operational complexity than WeKan/Planka.

### Source links
- WeKan API/docs:
  - https://wekan.github.io/api/v7.84/
  - https://wekan.github.io/wekan-doc/api/
- Vikunja docs:
  - https://vikunja.io/docs/api-documentation/
  - https://vikunja.io/docs/webhooks
- Planka docs:
  - https://docs.planka.cloud/docs/about-planka
  - https://docs.planka.cloud/docs/api-reference/swagger-ui
  - https://planka.app/docker
- NocoDB docs:
  - https://nocodb.com/docs/product-docs/views/view-types/kanban
  - https://nocodb.com/docs/product-docs/views
- Taiga docs:
  - https://docs.taiga.io/
  - https://docs.taiga.io/webhooks.html
- Plane docs:
  - https://developers.plane.so/
  - https://developers.plane.so/self-hosting/plane-architecture
