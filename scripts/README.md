# scripts/

Operational scripts that remain specific to CyberneticAgents.

## Canonical entrypoints (use these)

### Validation gate

- **`./scripts/quality_gate.sh`**
  - Runs nightly usability validation (`scripts/usability.sh`) in a synced local environment.

### Issue execution helper

- **`./scripts/execute_issue.sh <repo> <issue_number>`**
  - Framework for executing one issue directly on `main`.
  - Fetches/stores issue context under `.tmp/issues/`.
  - Optionally delegates to `scripts/issue_handlers/<issue_number>.sh`.

## Moved to standalone repository

The GitHub issue stage-label workflow engine was extracted from this repository.

Use:
- **`https://github.com/simonvanlaak/GhIssueWorkflow`**

That repo now owns:
- stage label ensure/pick/set logic
- owner authorization checks for `stage:ready-to-implement`
- workflow tick/queue orchestration
- closed-issue stage-label cleanup

## Legacy

- `scripts/_legacy/`
  - Archived historical workers and deprecated automation.
  - Reference only. Do not use for active automation.
