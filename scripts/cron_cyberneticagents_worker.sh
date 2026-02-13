#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PATH="/home/node/.local/bin:$PATH"

PYTHON="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  # Ensure the repo virtualenv exists (nightly script uses uv to build it).
  bash ./scripts/nightly-cyberneticagents.sh
fi

# Auth (non-interactive)
if [[ -z "${GH_TOKEN:-}" ]]; then
  export GH_TOKEN="$(op item get 'GitHub Personal Access Token' --vault OpenClaw --fields token --reveal 2>/dev/null || true)"
fi

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "ERROR: GH_TOKEN is empty and could not be loaded from 1Password" >&2
  exit 1
fi

gh auth status -h github.com >/dev/null

OWNER="simonvanlaak"
PROJECT_NUMBER=1
REPO="simonvanlaak/CyberneticAgents"

# Reduce GraphQL read calls:
# - Cache Project/Status field/option IDs locally (6h TTL)
# - If GraphQL budget is low, skip this run entirely.
RATE_REMAINING="$($PYTHON ./scripts/github_outbox.py drain --min-remaining 0 --max-ops 0 2>/dev/null | true)"
# (Drain is a no-op here; we rely on explicit gh rateLimit check below.)

RATE_JSON="$(gh api graphql -f query='{rateLimit{remaining resetAt}}')"
RATE_LEFT="$(echo "$RATE_JSON" | $PYTHON - <<'PY'
import json,sys
print(json.loads(sys.stdin.read())['data']['rateLimit']['remaining'])
PY
)"
RATE_RESET="$(echo "$RATE_JSON" | $PYTHON - <<'PY'
import json,sys
print(json.loads(sys.stdin.read())['data']['rateLimit']['resetAt'])
PY
)"

MIN_READ_BUDGET=200
if [[ "$RATE_LEFT" -lt "$MIN_READ_BUDGET" ]]; then
  echo "SKIP: GitHub GraphQL budget low (remaining=$RATE_LEFT resetAt=$RATE_RESET)" >&2
  exit 0
fi

# Source cached IDs as environment variables
# shellcheck disable=SC2046
source <($PYTHON ./scripts/github_project_cache.py --owner "$OWNER" --project-number "$PROJECT_NUMBER")

BACKLOG_OPTION_ID="$STATUS_OPTION_BACKLOG"
READY_OPTION_ID="$STATUS_OPTION_READY"
IN_PROGRESS_OPTION_ID="$STATUS_OPTION_IN_PROGRESS"
IN_REVIEW_OPTION_ID="$STATUS_OPTION_IN_REVIEW"
BLOCKED_OPTION_ID="$STATUS_OPTION_BLOCKED"

if [[ -z "${PROJECT_ID:-}" || -z "${STATUS_FIELD_ID:-}" || -z "$BACKLOG_OPTION_ID" || -z "$READY_OPTION_ID" || -z "$IN_PROGRESS_OPTION_ID" || -z "$IN_REVIEW_OPTION_ID" || -z "$BLOCKED_OPTION_ID" ]]; then
  echo "ERROR: Could not resolve project Status field/option IDs (cache)" >&2
  exit 1
fi

process_count=0
max_process=3

while [[ $process_count -lt $max_process ]]; do
  ITEMS_JSON="$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 200 --format json)"

  PICK_ID="$(echo "$ITEMS_JSON" | jq -r '.items[] | select(.status=="In progress") | .id' | head -n1)"
  PICK_STATUS="In progress"
  if [[ -z "$PICK_ID" || "$PICK_ID" == "null" ]]; then
    PICK_ID="$(echo "$ITEMS_JSON" | jq -r '.items[] | select(.status=="Ready") | .id' | head -n1)"
    PICK_STATUS="Ready"
  fi

  # Stop when there is no work
  if [[ -z "$PICK_ID" || "$PICK_ID" == "null" ]]; then
    exit 0
  fi

  ISSUE_NUMBER="$(echo "$ITEMS_JSON" | jq -r --arg id "$PICK_ID" '.items[] | select(.id==$id) | .content.number // empty')"
  TITLE="$(echo "$ITEMS_JSON" | jq -r --arg id "$PICK_ID" '.items[] | select(.id==$id) | .title')"

  # Status transitions (enqueue + drain to reduce GraphQL churn)
  if [[ "$PICK_STATUS" == "Ready" ]]; then
    "$PYTHON" ./scripts/github_outbox.py enqueue-status \
      --project-id "$PROJECT_ID" \
      --item-id "$PICK_ID" \
      --field-id "$STATUS_FIELD_ID" \
      --option-id "$IN_PROGRESS_OPTION_ID" \
      --quiet

    # Drain the status update if possible. If GitHub is throttling, skip this run
    # rather than claiming a status change that never happened.
    DRAIN_OUT="$("$PYTHON" ./scripts/github_outbox.py drain --min-remaining 50 --max-ops 10 2>&1)" || {
      echo "$DRAIN_OUT" >&2
      exit 1
    }
    if echo "$DRAIN_OUT" | grep -q '^SKIP '; then
      echo "$DRAIN_OUT" >&2
      exit 0
    fi
  fi

  # Baseline sync
  git fetch origin main >/dev/null 2>&1 || true
  git checkout main >/dev/null 2>&1 || true
  git pull --rebase origin main >/dev/null

  # Required quality gate before pushing code
  bash ./scripts/nightly-cyberneticagents.sh

  if [[ -z "$ISSUE_NUMBER" ]]; then
    # Blocked: no attached issue
    "$PYTHON" ./scripts/github_outbox.py enqueue-status \
      --project-id "$PROJECT_ID" \
      --item-id "$PICK_ID" \
      --field-id "$STATUS_FIELD_ID" \
      --option-id "$BACKLOG_OPTION_ID" \
      --quiet

    "$PYTHON" ./scripts/github_outbox.py drain --quiet || true

    echo "BLOCKED: Project item has no linked issue. Moved to Backlog: $TITLE" >&2
    exit 2
  fi

  # Attempt repo-provided automation if present; otherwise we just validate.
  if [[ -x ./scripts/auto-fix-issue.sh ]]; then
    ./scripts/auto-fix-issue.sh "$ISSUE_NUMBER" || true
  fi

  # Re-run quality gate after any modifications
  bash ./scripts/nightly-cyberneticagents.sh

  # If we changed files, commit them.
  if ! git diff --quiet; then
    git add -A
    # Link commit to issue number; allow no-op if another commit happened.
    git commit -m "chore: nightly auto-fix for issue #$ISSUE_NUMBER (#$ISSUE_NUMBER)" || true
  fi

  AHEAD_COUNT="$(git rev-list --count origin/main..HEAD)"
  if [[ "$AHEAD_COUNT" -gt 0 ]]; then
    git push origin main
  fi

  # Guardrail: do NOT move to In review when no code changes were produced.
  # This was causing churn (tickets land in In review with nothing to review).
  if [[ "$AHEAD_COUNT" -eq 0 ]]; then
    "$PYTHON" ./scripts/github_outbox.py enqueue-status \
      --project-id "$PROJECT_ID" \
      --item-id "$PICK_ID" \
      --field-id "$STATUS_FIELD_ID" \
      --option-id "$BLOCKED_OPTION_ID" \
      --quiet

    DRAIN_OUT="$("$PYTHON" ./scripts/github_outbox.py drain --min-remaining 50 --max-ops 10 2>&1)" || {
      echo "$DRAIN_OUT" >&2
      exit 1
    }
    if echo "$DRAIN_OUT" | grep -q '^SKIP '; then
      echo "$DRAIN_OUT" >&2
      exit 0
    fi

    # Avoid duplicate comments if the item keeps getting re-picked.
    LAST_BODY="$(gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=1" --jq '.[0].body' 2>/dev/null || true)"
    if echo "$LAST_BODY" | grep -q '^Moved to Blocked via automation:'; then
      process_count=$((process_count + 1))
      continue
    fi

    gh issue comment "$ISSUE_NUMBER" --repo "$REPO" --body "Moved to Blocked via automation: no code changes were produced.

I ran ./scripts/nightly-cyberneticagents.sh, but there were no commits to review.

This likely needs human input (clarify requirements) or a non-automatable implementation step.

Please add:
- Expected outcome + acceptance criteria
- Any pointers (files/paths) or constraints
- If this is a docs-only / no-code task, explicitly say so and describe what 'done' looks like."

    process_count=$((process_count + 1))
    continue
  fi

  "$PYTHON" ./scripts/github_outbox.py enqueue-status \
    --project-id "$PROJECT_ID" \
    --item-id "$PICK_ID" \
    --field-id "$STATUS_FIELD_ID" \
    --option-id "$IN_REVIEW_OPTION_ID" \
    --quiet

  DRAIN_OUT="$("$PYTHON" ./scripts/github_outbox.py drain --min-remaining 50 --max-ops 10 2>&1)" || {
    echo "$DRAIN_OUT" >&2
    exit 1
  }
  if echo "$DRAIN_OUT" | grep -q '^SKIP '; then
    echo "$DRAIN_OUT" >&2
    exit 0
  fi

  RECENT_SHAS="$(git log --format=%H -n 5)"
  gh issue comment "$ISSUE_NUMBER" --repo "$REPO" --body "Moved to In review via nightly automation.

Summary:
- Ran ./scripts/nightly-cyberneticagents.sh
- Applied any safe auto-fixes (if available)

Recent commits:
$(echo "$RECENT_SHAS" | sed 's/^/- /')

Validation:
- Pull main and re-run: bash ./scripts/nightly-cyberneticagents.sh"

  process_count=$((process_count + 1))
done
