#!/usr/bin/env bash
set -euo pipefail

# Monitor: "automation is idle" for CyberneticAgents, without GitHub Search API.
#
# Why this exists:
# - GitHub REST Search endpoints are easy to misuse with `gh api`.
#   If you pass fields (`-f` or `-F`) without forcing `-X GET`, `gh api` will
#   default to POST, and GitHub responds with 404/422 (depending on endpoint).
# - This script avoids Search entirely and instead uses:
#     GET /repos/{owner}/{repo}/issues?state=open&labels=...
#   with pagination.
#
# Notes:
# - REST "List repository issues" returns both issues and PRs; we exclude PRs.
# - Keep it cheap: we only fetch issue numbers (one per line).
# - Designed for cron usage: low-noise, transition-only notification with a stamp file.

REPO="${REPO:-simonvanlaak/CyberneticAgents}"
TO_CHAT_ID="${TO_CHAT_ID:-5488423581}"   # used only by callers that send notifications
STAMP_FILE="${STAMP_FILE:-/root/.openclaw/workspace/.tmp/automation_idle_last_notified_utc.txt}"
DEDUPE_HOURS="${DEDUPE_HOURS:-12}"

count_open_issues_with_label() {
  local label="$1"

  # Important: force GET. With -f/-F, gh defaults to POST otherwise.
  gh api -X GET "repos/${REPO}/issues" \
    -F state=open \
    -F labels="$label" \
    -F per_page=100 \
    --paginate \
    --jq '.[] | select(.pull_request == null) | .number' \
    | wc -l | tr -d ' '
}

utc_now_iso() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

stamp_recent_enough() {
  # Returns 0 (true) if stamp exists and is within DEDUPE_HOURS.
  [[ -f "$STAMP_FILE" ]] || return 1

  local stamp
  stamp="$(cat "$STAMP_FILE" 2>/dev/null || true)"
  [[ -n "$stamp" ]] || return 1

  local stamp_epoch now_epoch
  stamp_epoch=$(date -u -d "$stamp" +%s 2>/dev/null || echo 0)
  now_epoch=$(date -u +%s)

  local max_age
  max_age=$(( DEDUPE_HOURS * 3600 ))

  (( stamp_epoch > 0 )) || return 1
  (( now_epoch - stamp_epoch < max_age ))
}

main() {
  mkdir -p "$(dirname "$STAMP_FILE")"

  local queued ready in_progress needs_clarification in_review blocked
  queued=$(count_open_issues_with_label "stage:queued")
  ready=$(count_open_issues_with_label "stage:ready-to-implement")
  in_progress=$(count_open_issues_with_label "stage:in-progress")

  needs_clarification=$(count_open_issues_with_label "stage:needs-clarification")
  in_review=$(count_open_issues_with_label "stage:in-review")
  blocked=$(count_open_issues_with_label "stage:blocked")

  echo "queued=${queued}, ready-to-implement=${ready}, in-progress=${in_progress}, needs-clarification=${needs_clarification}, in-review=${in_review}, blocked=${blocked}."

  local is_idle=0
  if [[ "$queued" == "0" && "$ready" == "0" && "$in_progress" == "0" ]]; then
    is_idle=1
  fi

  if [[ "$is_idle" == "1" ]]; then
    if stamp_recent_enough; then
      echo "Idle state detected, but deduped (stamp < ${DEDUPE_HOURS}h)."
      exit 0
    fi

    # Caller decides how to notify (voice note, message, etc.).
    echo "IDLE_TRANSITION: Automation is idle. waiting: needs-clarification=${needs_clarification}, in-review=${in_review}, blocked=${blocked}."
    utc_now_iso >"$STAMP_FILE"
    exit 0
  fi

  # Not idle: clear stamp so next idle transition can notify.
  : >"$STAMP_FILE"
  echo "Not idle -> cleared stamp."
}

main "$@"
