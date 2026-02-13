#!/usr/bin/env bash
set -euo pipefail

cd /root/.openclaw/workspace

export PATH="/home/node/.local/bin:$PATH"

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

PROJECT_ID="$(gh project view "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.id')"
STATUS_FIELD_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .id')"

opt_id() {
  gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq ".fields[] | select(.name==\"Status\") | .options[] | select(.name==\"$1\") | .id"
}

BACKLOG_OPTION_ID="$(opt_id Backlog)"
READY_OPTION_ID="$(opt_id Ready)"
IN_PROGRESS_OPTION_ID="$(opt_id 'In progress')"
IN_REVIEW_OPTION_ID="$(opt_id 'In review')"
BLOCKED_OPTION_ID="$(opt_id Blocked)"

if [[ -z "$STATUS_FIELD_ID" || -z "$BACKLOG_OPTION_ID" || -z "$READY_OPTION_ID" || -z "$IN_PROGRESS_OPTION_ID" || -z "$IN_REVIEW_OPTION_ID" || -z "$BLOCKED_OPTION_ID" ]]; then
  echo "ERROR: Could not resolve project Status field/option IDs" >&2
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

  # Status transitions
  if [[ "$PICK_STATUS" == "Ready" ]]; then
    gh project item-edit \
      --id "$PICK_ID" \
      --project-id "$PROJECT_ID" \
      --field-id "$STATUS_FIELD_ID" \
      --single-select-option-id "$IN_PROGRESS_OPTION_ID" \
      >/dev/null
  fi

  # Baseline sync
  git fetch origin main >/dev/null 2>&1 || true
  git checkout main >/dev/null 2>&1 || true
  git pull --rebase origin main >/dev/null

  # Required quality gate before pushing code
  bash ./scripts/nightly-cyberneticagents.sh

  if [[ -z "$ISSUE_NUMBER" ]]; then
    # Blocked: no attached issue
    gh project item-edit \
      --id "$PICK_ID" \
      --project-id "$PROJECT_ID" \
      --field-id "$STATUS_FIELD_ID" \
      --single-select-option-id "$BACKLOG_OPTION_ID" \
      >/dev/null

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
    gh project item-edit \
      --id "$PICK_ID" \
      --project-id "$PROJECT_ID" \
      --field-id "$STATUS_FIELD_ID" \
      --single-select-option-id "$BLOCKED_OPTION_ID" \
      >/dev/null

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

  gh project item-edit \
    --id "$PICK_ID" \
    --project-id "$PROJECT_ID" \
    --field-id "$STATUS_FIELD_ID" \
    --single-select-option-id "$IN_REVIEW_OPTION_ID" \
    >/dev/null

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
