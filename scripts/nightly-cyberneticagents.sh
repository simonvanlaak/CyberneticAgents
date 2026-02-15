#!/usr/bin/env bash
set -euo pipefail

# Canonical nightly entrypoint.
# Delegates to the lock-protected wrapper so cron/manual execution uses
# identical singleton behavior.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

bash ./scripts/run_project_automation.sh
