# Product Requirements Document – Standard Operating Procedures (SOPs)

## Problem Statement
Teams need repeatable, governed procedures that can be created and managed by the VSM itself. Today, recurring work is represented as initiatives and tasks, but there is no reusable template layer with approvals, risk metadata, or auditability across runs.

## Goals
- Enable systems to create, approve, and execute Standard Operating Procedures (SOPs).
- Keep procedures aligned with the existing initiative/task structure.
- Provide governance and traceability for the procedure lifecycle and runs.
- Allow procedure execution to materialize standard initiatives and tasks.

## Non‑Goals
- Replace the existing initiative/task runtime model.
- Provide a user‑facing procedure editor UI in this phase.
- Implement manual CAB workflows beyond System5 approvals.

## Conceptual Model
- A **Standard Operating Procedure (SOP)** is a reusable initiative template.
- **Procedure task templates** represent the task structure inside the procedure.
- A **procedure run** is an execution instance that materializes an initiative and tasks from the template.

## Functional Requirements
1. **Procedure Lifecycle**
- Procedures have explicit states: `draft`, `approved`, `retired`.
- Procedures must record `version`, `created_by_system_id`, `approved_by_system_id`, and timestamps.

2. **Template Structure**
- Each procedure contains a list of task templates with ordering and optional dependencies.
- Task templates mirror the fields needed to create standard tasks.

3. **Execution**
- Executing a procedure creates a new initiative and tasks from the template.
- The initiative must reference the procedure and procedure version.

4. **Approvals**
- System4 can draft procedures.
- System5 approves procedures and changes procedure state to `approved`.
- Only `approved` procedures are eligible for execution.

5. **Risk Metadata**
- Procedures must include `risk_level` and `impact` fields.
- Procedures must include `rollback_plan` for recoverability.

6. **Post‑Run Review**
- Procedure executions use the existing initiative post‑run review workflow.
- Reviews should include procedure‑specific context and link back to the procedure and run.

## Data Model (Proposed)
1. **procedures**
- `id`, `team_id`, `name`, `description`
- `status`, `version`
- `risk_level`, `impact`, `rollback_plan`
- `created_by_system_id`, `approved_by_system_id`
- `created_at`, `updated_at`

2. **procedure_tasks**
- `id`, `procedure_id`
- `name`, `description`
- `position`, `depends_on_task_id`
- `default_assignee_system_type` (optional)
- `required_skills` (optional)

3. **procedure_runs**
- `id`, `procedure_id`, `procedure_version`
- `initiative_id`
- `status` (started, completed, failed)
- `started_at`, `completed_at`

## VSM Responsibility Mapping
- System4: draft procedures based on recurring work and observations.
- System5: approve procedures, enforce policy constraints.
- System3: decide when to execute procedures.
- System1: execute tasks generated from procedures.

## Acceptance Criteria
- A procedure can be created, approved, and executed end‑to‑end.
- Procedure execution materializes an initiative and tasks that match the template.
- Procedure metadata is traceable from the initiative run.
- Procedures cannot be executed unless approved.
- Procedure post‑run review is recorded with the existing initiative review flow.

## Open Questions
- Do we need per‑task overrides at execution time?
- Should procedure versions be immutable once approved?
- How should procedure deprecation and migrations be handled?

## Decisions
### Per‑Task Overrides
The procedure is a template only. Once a procedure is materialized into an initiative, System3 can adjust tasks using the existing initiative workflow. No additional override mechanism is required in the procedure template or execution path.

### Version Immutability
Approved procedure versions are immutable. Editing creates a new draft version. When a new version is approved, the prior approved version is retired for new runs but retained for audit.

### Deprecation & Migrations
Retired procedure versions are blocked from execution. They remain discoverable by System4 for analysis and learning only. New runs must use the latest approved version.
