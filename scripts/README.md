# scripts/

This folder contains operational scripts for the CyberneticAgents repo.

## Canonical entrypoints (use these)

### Project automation tick (cron + manual)

- **`./scripts/run_project_automation.sh`**
  - Enforces repo-root execution
  - Enforces singleton lock: `/tmp/cyberneticagents-project-worker.lock`
  - Runs one tick of the worker (`cron_cyberneticagents_worker.sh`)

### Worker tick implementation

- **`./scripts/cron_cyberneticagents_worker.sh`**
  - Source of truth: **GitHub Issue labels** (NOT GitHub Projects)
  - Status labels (single-select):
    - `status:ready`
    - `status:in-progress`
    - `status:in-review`
    - `status:blocked`

### Quality gate

- **`./scripts/quality_gate.sh`**
  - Runs the quality gate (tests/usability) used by automation before pushing.

## Utilities

- **`./scripts/github_issue_queue.py`**
  - Ensure labels exist
  - Pick next issue (`status:in-progress` first, else `status:ready`)
  - Set status label (single-select)

## Legacy

- `scripts/_legacy/`
  - Old automation scripts kept for reference.
  - In particular, `scripts/_legacy/projects_v2/` contains the deprecated GitHub Projects v2 + GraphQL-based worker.
  - New automation should not depend on it.
