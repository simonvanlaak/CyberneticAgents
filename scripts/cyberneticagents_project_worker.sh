#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/node/.local/bin:$PATH"

# Auth (non-interactive)
if [[ -z "${GH_TOKEN:-}" ]]; then
  if command -v op >/dev/null 2>&1; then
    # Do not print token
    GH_TOKEN_VAL="$(op item get "GitHub Personal Access Token" --vault OpenClaw --fields token --reveal 2>/dev/null || true)"
    if [[ -n "$GH_TOKEN_VAL" ]]; then
      export GH_TOKEN="$GH_TOKEN_VAL"
    fi
  fi
fi

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "GH_TOKEN is empty and could not be loaded from 1Password (op)." >&2
  exit 1
fi

if ! gh auth status -h github.com >/dev/null 2>&1; then
  echo "gh not authenticated (gh auth status failed)." >&2
  exit 1
fi

# Locate repo
if [[ -d /root/.openclaw/workspace/CyberneticAgents/.git ]]; then
  cd /root/.openclaw/workspace/CyberneticAgents
elif [[ -d /root/.openclaw/workspace/.git ]]; then
  cd /root/.openclaw/workspace
else
  echo "Could not locate CyberneticAgents git repo under /root/.openclaw/workspace" >&2
  exit 1
fi

# Main-only workflow: sync main
git fetch origin --prune >/dev/null 2>&1 || true
if git show-ref --verify --quiet refs/remotes/origin/main; then
  git checkout -B main origin/main >/dev/null 2>&1
else
  echo "origin/main not found; expected main-only workflow" >&2
  exit 1
fi

project_items_json() {
  gh project item-list 1 --owner simonvanlaak --limit 200 --format json
}

pick_item() {
  # stdin: project JSON -> stdout: picked item JSON; exit 2 if none
  node -e '
    const fs = require("fs");
    const input = fs.readFileSync(0, "utf8");
    if (!input.trim()) process.exit(1);
    const data = JSON.parse(input);
    const items = data.items || [];
    const pick = (status) => items.find(it => it && it.status === status);
    const it = pick("In progress") || pick("Ready");
    if (!it) process.exit(2);
    process.stdout.write(JSON.stringify(it));
  '
}

jget() {
  # usage: jget '<json>' '<js expression on j>'
  local json="$1"
  local expr="$2"
  node -e "const j=JSON.parse(process.argv[1]); const v=(${expr}); if (v===undefined||v===null) process.exit(3); process.stdout.write(String(v));" "$json"
}

move_status() {
  local item_id="$1"
  local status="$2"
  gh project item-edit 1 --owner simonvanlaak --id "$item_id" --field Status --text "$status" >/dev/null
}

comment_issue() {
  local issue_url="$1"
  local body="$2"
  gh issue comment "$issue_url" --body "$body" >/dev/null
}

while true; do
  items_json="$(project_items_json)"

  set +e
  picked_json="$(printf '%s' "$items_json" | pick_item)"
  pick_rc=$?
  set -e

  if [[ $pick_rc -eq 2 ]]; then
    exit 0
  fi
  if [[ $pick_rc -ne 0 ]]; then
    echo "Failed to pick project item (rc=$pick_rc)" >&2
    exit 1
  fi

  item_id="$(jget "$picked_json" 'j.id')"
  item_status="$(jget "$picked_json" 'j.status || ""')"
  content_url="$(jget "$picked_json" '(j.content && j.content.url) || ""')"
  content_type="$(jget "$picked_json" '(j.content && j.content.type) || ""')"

  if [[ -z "$item_id" || -z "$content_url" ]]; then
    echo "Malformed project item (missing id/url)" >&2
    exit 1
  fi

  # Status transitions
  if [[ "$item_status" == "Ready" ]]; then
    move_status "$item_id" "In progress"
  fi

  if [[ "$content_type" != "Issue" ]]; then
    move_status "$item_id" "Backlog"
    comment_issue "$content_url" "Moved to Backlog: automation currently supports only GitHub Issues (got content type: $content_type). What should I do with this item?" || true
    continue
  fi

  issue_json="$(gh issue view "$content_url" --json number,title,url)"
  issue_number="$(jget "$issue_json" 'j.number')"
  issue_title="$(jget "$issue_json" 'j.title')"

  # Quality: run nightly script before pushing
  set +e
  bash ./scripts/nightly-cyberneticagents.sh
  script_rc=$?
  set -e

  if [[ $script_rc -ne 0 ]]; then
    move_status "$item_id" "Backlog"
    comment_issue "$content_url" "Moved to Backlog: ./scripts/nightly-cyberneticagents.sh failed (exit $script_rc).\n\nQuestions:\n- Any prerequisites missing on the runner?\n- Should this item be handled manually?" || true
    git reset --hard >/dev/null 2>&1 || true
    continue
  fi

  # Commit/push directly to main if changes exist
  if ! git diff --quiet || ! git diff --cached --quiet; then
    git add -A
    if ! git diff --cached --quiet; then
      msg="CyberneticAgents: ${issue_title} (#${issue_number})"
      git commit -m "$msg" >/dev/null
      sha="$(git rev-parse HEAD)"
      git push origin main >/dev/null

      move_status "$item_id" "In review"
      comment_issue "$content_url" "Moved to In review.\n\nSummary: Ran ./scripts/nightly-cyberneticagents.sh and committed changes.\nValidation: ./scripts/nightly-cyberneticagents.sh (exit 0).\nCommit: $sha" || true
    fi
  else
    move_status "$item_id" "In review"
    comment_issue "$content_url" "Moved to In review.\n\nSummary: Ran ./scripts/nightly-cyberneticagents.sh; no repo changes were produced.\nValidation: ./scripts/nightly-cyberneticagents.sh (exit 0)." || true
  fi

done
