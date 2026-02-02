# Standard Operating Procedures

## Overview
Standard Operating Procedures (SOPs) provide a reusable template layer for recurring work.
An SOP can be drafted, approved, executed, and audited. Executions materialize an initiative
and its tasks from the template while preserving traceability to the procedure version.

## Lifecycle
- Draft procedures in System4.
- Approve procedures in System5 (approval retires the prior approved version in the series).
- Execute approved procedures in System3.
- Retired procedures remain discoverable for analysis but cannot be executed.

## Data Model
- `procedures`: procedure metadata, versioning, status, risk, and governance fields.
- `procedure_tasks`: ordered task templates with optional dependencies and skill metadata.
- `procedure_runs`: execution instances linking procedures to initiatives.

## Execution Flow
1. System4 creates a draft procedure with task templates.
2. System5 approves the draft and retires any previously approved version.
3. System3 executes the approved procedure:
   - Creates a new initiative.
   - Materializes tasks from the template.
   - Records a procedure run.

## Governance & Traceability
- Procedures are versioned and immutable once approved.
- Initiatives created from SOPs carry `procedure_id` and `procedure_version`.
- Procedure runs link execution instances back to the originating SOP version.

## Interfaces
- System4 tools: create draft, revise draft, search procedures.
- System5 tools: approve procedure.
- System3 tools: execute procedure.

## Notes
- Task overrides happen after materialization using standard initiative workflows.
- Procedure runs use the existing initiative review flow for post-run review.
