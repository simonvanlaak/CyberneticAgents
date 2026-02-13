#!/usr/bin/env bash
set -euo pipefail

# Single entrypoint wrapper for CyberneticAgents project automation.
#
# Purpose:
# - Hard-enforce running from the CyberneticAgents repo root
# - Provide a stable command for cron/jobs to invoke
# - Preserve the singleton/no-overlap rule via flock

export PATH="/home/node/.local/bin:$PATH"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOCKFILE="/tmp/cyberneticagents-project-worker.lock"

# Non-blocking singleton guard. If lock is held, exit silently.
flock -n "$LOCKFILE" -c 'bash ./scripts/cron_cyberneticagents_worker.sh' || exit 0
