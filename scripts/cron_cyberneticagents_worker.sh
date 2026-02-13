#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PATH="/home/node/.local/bin:$PATH"

PYTHON="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  # Ensure the repo virtualenv exists (quality gate uses uv to build it).
  bash ./scripts/quality_gate.sh
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

REPO="simonvanlaak/CyberneticAgents"

# Source of truth: GitHub Issues labels (NOT GitHub Projects).
# We fully ignore Projects going forward due to Projects v2 GraphQL rate limiting.
"$PYTHON" ./scripts/github_issue_queue.py --repo "$REPO" ensure-labels >/dev/null

STATUS_READY="status:ready"
STATUS_IN_PROGRESS="status:in-progress"
STATUS_IN_REVIEW="status:in-review"
STATUS_BLOCKED="status:blocked"

process_count=0
max_process=3

while [[ $process_count -lt $max_process ]]; do
  PICK_JSON="$("$PYTHON" ./scripts/github_issue_queue.py --repo "$REPO" pick-next 2>/dev/null || true)"

  if [[ -z "$PICK_JSON" ]]; then
    exit 0
  fi

  ISSUE_NUMBER="$(printf '%s' "$PICK_JSON" | "$PYTHON" -c 'import json,sys; print(json.loads(sys.stdin.read())["number"])')"

  TITLE="$(printf '%s' "$PICK_JSON" | "$PYTHON" -c 'import json,sys; print(json.loads(sys.stdin.read())["title"])')"

  PICKED_FROM_STATUS="$(printf '%s' "$PICK_JSON" | "$PYTHON" -c 'import json,sys; print(json.loads(sys.stdin.read())["picked_from_status"])')"

  if [[ "$PICKED_FROM_STATUS" == "$STATUS_READY" ]]; then
    "$PYTHON" ./scripts/github_issue_queue.py --repo "$REPO" set-status --issue "$ISSUE_NUMBER" --status "$STATUS_IN_PROGRESS"
  fi

  # Baseline sync
  git fetch origin main >/dev/null 2>&1 || true
  git checkout main >/dev/null 2>&1 || true
  git pull --rebase origin main >/dev/null

  # Required quality gate before pushing code
  bash ./scripts/quality_gate.sh

  if [[ -z "$ISSUE_NUMBER" ]]; then
    echo "ERROR: picked issue missing number" >&2
    exit 2
  fi

  # Execute the issue (framework). For feature work, the calling agent is expected
  # to implement changes + create multiple atomic commits.
  if [[ -x ./scripts/execute_issue.sh ]]; then
    set +e
    ./scripts/execute_issue.sh "$REPO" "$ISSUE_NUMBER"
    EXEC_RC=$?
    set -e

    if [[ "$EXEC_RC" -ne 0 && "$EXEC_RC" -ne 4 ]]; then
      # Hard failure inside executor.
      echo "ERROR: execute_issue.sh failed rc=$EXEC_RC for #$ISSUE_NUMBER" >&2
      exit 1
    fi
  fi

  # Re-run quality gate after any modifications
  bash ./scripts/quality_gate.sh

  # Commit/push policy:
  # - We want frequent, atomic commits while working an issue.
  # - Therefore, this worker should NOT auto-commit "git add -A" as a single lump.
  # - Instead, the issue-specific automation (./scripts/auto-fix-issue.sh) must create
  #   atomic commits as it makes changes.
  # - If there are uncommitted changes at this point, block the issue and ask for
  #   proper commit scoping.
  if ! git diff --quiet; then
    "$PYTHON" ./scripts/github_issue_queue.py --repo "$REPO" set-status --issue "$ISSUE_NUMBER" --status "$STATUS_BLOCKED"

    gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments" -f body="Blocked by automation: working tree has uncommitted changes.

Please commit changes as small, atomic commits linked to #$ISSUE_NUMBER (per AGENTS.md), then re-label this issue as status:ready.

Validation run so far:
- bash ./scripts/quality_gate.sh" >/dev/null

    process_count=$((process_count + 1))
    continue
  fi

  AHEAD_COUNT="$(git rev-list --count origin/main..HEAD)"

  # Always push at the end of working an issue *when there are commits*.
  if [[ "$AHEAD_COUNT" -gt 0 ]]; then
    git push origin main
  fi

  # Guardrail: do NOT move to In review when no code changes were produced.
  # This was causing churn (tickets land in In review with nothing to review).
  if [[ "$AHEAD_COUNT" -eq 0 ]]; then
    "$PYTHON" ./scripts/github_issue_queue.py --repo "$REPO" set-status --issue "$ISSUE_NUMBER" --status "$STATUS_BLOCKED"

    # Avoid duplicate comments if the issue keeps getting re-picked.
    LAST_BODY="$(gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=1" --jq '.[0].body' 2>/dev/null || true)"
    if echo "$LAST_BODY" | grep -q '^Moved to Blocked via automation:'; then
      process_count=$((process_count + 1))
      continue
    fi

    # Post comment via REST API (avoid Projects/GraphQL throttling issues).
    gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments" -f body="Moved to Blocked via automation: no code changes were produced.

I ran ./scripts/quality_gate.sh, but there were no commits to review.

This likely needs human input (clarify requirements) or a non-automatable implementation step.

Please add:
- Expected outcome + acceptance criteria
- Any pointers (files/paths) or constraints
- If this is a docs-only / no-code task, explicitly say so and describe what 'done' looks like." >/dev/null

    process_count=$((process_count + 1))
    continue
  fi

  "$PYTHON" ./scripts/github_issue_queue.py --repo "$REPO" set-status --issue "$ISSUE_NUMBER" --status "$STATUS_IN_REVIEW"

  RECENT_SHAS="$(git log --format=%H -n 5)"
  BODY="Moved to In review via nightly automation.

Summary:
- Ran ./scripts/quality_gate.sh
- Applied any safe auto-fixes (if available)

Recent commits:
$(echo "$RECENT_SHAS" | sed 's/^/- /')

Validation:
- Pull main and re-run: bash ./scripts/quality_gate.sh"

  # Post comment via REST API.
  gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments" -f body="$BODY" >/dev/null

  process_count=$((process_count + 1))
done
