#!/usr/bin/env bash
set -euo pipefail

# Poll GitHub Project for work (Ready/In progress) and trigger the OpenClaw cron worker
# WITHOUT invoking any LLM when there's nothing to do.
#
# Intended to be run by the host OS scheduler (system cron) every 30 minutes.

PROJECT_NUMBER="1"
OWNER="@me"
REPO="simonvanlaak/CyberneticAgents"
WORKER_JOB_ID="876ab72b-e84f-4a5c-8620-9996bf625ccd"

# Where to run the worker from (best-effort)
WORKDIR_1="/home/simon/.openclaw/workspace/CyberneticAgents"
WORKDIR_2="/home/node/.openclaw/workspace/CyberneticAgents"

log() { echo "[poll] $*"; }

# Ensure gh is available
command -v gh >/dev/null 2>&1 || { log "gh not found"; exit 2; }

# Quick auth check; do not prompt interactively
if ! gh auth status -h github.com >/dev/null 2>&1; then
  log "gh not authenticated (non-interactive)";
  exit 2
fi

# Fetch project items and look for work
# Note: `gh project item-list` requires `project` scope.
# If your token lacks it, refresh interactively once: `gh auth refresh -s project`.
items_json="$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 200 --format json 2>/dev/null || true)"
if [ -z "$items_json" ]; then
  log "could not list project items (missing scope?)"
  exit 2
fi

has_work="$(printf "%s" "$items_json" | python3 - <<'PY'
import json,sys
items=json.load(sys.stdin).get('items',[])
for it in items:
  st=(it.get('status') or '').strip().lower()
  if st in ('ready','in progress'):
    print('yes')
    break
PY
)"

if [ "$has_work" != "yes" ]; then
  # Nothing to do: exit without triggering anything.
  exit 0
fi

# Trigger the OpenClaw worker job.
# IMPORTANT: the exact CLI subcommand may vary by install.
# Expected form is something like:
#   openclaw cron run --id <jobId>
# If your CLI differs, adjust the command below accordingly.

if command -v openclaw >/dev/null 2>&1; then
  log "work detected; triggering worker job ${WORKER_JOB_ID} via openclaw CLI"
  openclaw cron run --id "$WORKER_JOB_ID"
  exit 0
fi

log "work detected but openclaw CLI not found; cannot trigger worker"
exit 2
