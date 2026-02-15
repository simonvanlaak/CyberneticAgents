# scripts/

Operational automation scripts for CyberneticAgents.

## Canonical entrypoints (use these)

### Nightly cron payload

- **`./scripts/nightly-cyberneticagents.sh`**
  - Canonical cron target.
  - Delegates to `run_project_automation.sh` so cron/manual runs share lock behavior.

### Project automation lock wrapper

- **`./scripts/run_project_automation.sh`**
  - Enforces repo-root execution.
  - Enforces singleton lock: `/tmp/cyberneticagents-project-worker.lock`.
  - Executes one worker tick (`cron_cyberneticagents_worker.sh`).

### Worker tick implementation

- **`./scripts/cron_cyberneticagents_worker.sh`**
  - Source of truth: GitHub Issue stage labels (`stage:*`), not GitHub Projects.
  - Stage labels:
    - `stage:backlog`
    - `stage:needs-clarification`
    - `stage:ready-to-implement`
    - `stage:in-progress`
    - `stage:in-review`
    - `stage:blocked`

### Validation gate

- **`./scripts/quality_gate.sh`**
  - Runs nightly usability validation (`scripts/usability.sh`) in a synced local environment.

## Supporting utilities

- **`./scripts/execute_issue.sh <repo> <issue_number>`**
  - Framework for executing one issue directly on `main`.
  - Fetches/stores issue context under `.tmp/issues/`.
  - Optionally delegates to `scripts/issue_handlers/<issue_number>.sh`.

- **`./scripts/github_issue_queue.py`**
  - Ensures stage labels exist.
  - Picks the next issue by stage priority.
  - Sets exactly one stage label atomically.

## Legacy

- `scripts/_legacy/`
  - Archived historical workers and deprecated Project v2/GraphQL automation.
  - Reference only. Do not use for active automation.
