#!/usr/bin/env bash
set -euo pipefail

cd /root/.openclaw/workspace

export PATH="/home/node/.local/bin:$PATH"

# Non-interactive GH auth
if [ -z "${GH_TOKEN:-}" ]; then
  # Non-interactive: fetch from 1Password.
  # Note: do NOT echo the token.
  export GH_TOKEN="$(op item get 'GitHub Personal Access Token' --vault OpenClaw --fields token --reveal 2>/dev/null | tr -d '\r\n')"

  if [ -z "${GH_TOKEN:-}" ]; then
    echo "Unexpected: GH_TOKEN was empty and 1Password lookup returned empty. Is op signed in/unlocked (or is the item/vault name wrong)?"
    exit 2
  fi
fi

if ! gh auth status -h github.com >/dev/null 2>&1; then
  echo "Unexpected: gh is not authenticated for github.com (GH_TOKEN invalid/missing)."
  exit 2
fi

OWNER="simonvanlaak"
PROJECT_NUMBER=1
REPO="simonvanlaak/CyberneticAgents"

PROJECT_ID="$(gh project view "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.id')"
STATUS_FIELD_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .id')"
BACKLOG_OPTION_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .options[] | select(.name=="Backlog") | .id')"
IN_PROGRESS_OPTION_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .options[] | select(.name=="In progress") | .id')"
IN_REVIEW_OPTION_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .options[] | select(.name=="In review") | .id')"

# main-only workflow
# Ensure a clean working tree; this automation is intended to run on a pristine checkout.
# (Avoids `git pull --rebase` failing due to leftover unstaged changes from prior runs.)
git fetch origin main --quiet || true
git checkout -q main || true
git reset --hard -q
git clean -fdq
git pull --rebase --quiet origin main || true

while true; do
  ITEMS_JSON="$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 200 --format json)"

  PICKED="$(printf "%s" "$ITEMS_JSON" | jq -r '(.items | map(select(.status=="In progress")) | .[0]) // (.items | map(select(.status=="Ready")) | .[0]) // empty')"

  if [ -z "$PICKED" ] || [ "$PICKED" = "null" ]; then
    exit 0
  fi

  ITEM_ID="$(printf "%s" "$PICKED" | jq -r '.id')"
  ITEM_STATUS="$(printf "%s" "$PICKED" | jq -r '.status')"
  ISSUE_NUMBER="$(printf "%s" "$PICKED" | jq -r '.content.number // empty')"
  TITLE="$(printf "%s" "$PICKED" | jq -r '.title')"

  if [ -z "$ISSUE_NUMBER" ] || [ "$ISSUE_NUMBER" = "null" ]; then
    echo "Unexpected: picked project item has no linked issue: $TITLE ($ITEM_ID)"
    exit 2
  fi

  if [ "$ITEM_STATUS" = "Ready" ]; then
    gh project item-edit --id "$ITEM_ID" --project-id "$PROJECT_ID" --field-id "$STATUS_FIELD_ID" --single-select-option-id "$IN_PROGRESS_OPTION_ID" >/dev/null
  fi

  # clean slate per ticket
  git reset --hard -q
  git clean -fdq
  git pull --rebase --quiet origin main || true

  LOG="/tmp/nightly-cyberneticagents-$ISSUE_NUMBER.log"
  if ! bash ./scripts/nightly-cyberneticagents.sh >"$LOG" 2>&1; then
    gh project item-edit --id "$ITEM_ID" --project-id "$PROJECT_ID" --field-id "$STATUS_FIELD_ID" --single-select-option-id "$BACKLOG_OPTION_ID" >/dev/null
    TAIL="$(tail -n 60 "$LOG")"
    gh issue comment "$ISSUE_NUMBER" --repo "$REPO" --body "Moved to Backlog: nightly automation failed for **$TITLE**.

Tail of log (last 60 lines):

```
$TAIL
```

Questions:
- Is there any expected env/setup change?
- Should this ticket be split or have manual steps?" >/dev/null

    echo "Moved issue #$ISSUE_NUMBER to Backlog due to automation failure. Needs attention."
    exit 1
  fi

  if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "chore: nightly usability auto-fix (#$ISSUE_NUMBER)" >/dev/null

    # required pre-push run
    bash ./scripts/nightly-cyberneticagents.sh >/dev/null 2>&1

    git push -q origin main
    COMMIT_SHA="$(git rev-parse HEAD)"
    COMMENT="Automation complete for **$TITLE**.

- Ran nightly usability + auto-fix
- Changes committed + pushed to main

Commit: $COMMIT_SHA"
  else
    COMMENT="Automation complete for **$TITLE**.

- Ran nightly usability + auto-fix
- No code changes were necessary."
  fi

  gh project item-edit --id "$ITEM_ID" --project-id "$PROJECT_ID" --field-id "$STATUS_FIELD_ID" --single-select-option-id "$IN_REVIEW_OPTION_ID" >/dev/null
  gh issue comment "$ISSUE_NUMBER" --repo "$REPO" --body "$COMMENT" >/dev/null

done
