#!/usr/bin/env bash
set -euo pipefail

# CyberneticAgents GitHub Project worker
# - Processes items in Project #1 (owner: simonvanlaak)
# - Prefers Status=="In progress", else Status=="Ready"
# - Moves Ready -> In progress immediately
# - When complete: In progress -> In review
# - When blocked: move to Backlog + leave explicit questions
#
# NOTE: This script is designed to run non-interactively (cron/CI). It avoids jq
# and uses python3 for JSON parsing to keep dependencies minimal.

OWNER="simonvanlaak"
PROJECT_NUMBER="1"
REPO_DIR="/root/.openclaw/workspace/CyberneticAgents"

export PATH="/home/node/.local/bin:$PATH"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: missing required command: $1" >&2; exit 1; }
}

require_cmd gh
require_cmd python3

# ---- Auth (non-interactive) ----
if [[ -z "${GH_TOKEN:-}" ]]; then
  require_cmd op
  # Do NOT print token.
  GH_TOKEN="$(op item get 'GitHub Personal Access Token' --vault OpenClaw --fields token --reveal 2>/dev/null || true)"
  export GH_TOKEN
fi

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "ERROR: GH_TOKEN is empty and could not be loaded from 1Password." >&2
  exit 1
fi

gh auth status -h github.com >/dev/null

# ---- Repo ----
cd "$REPO_DIR"

git config --global --add safe.directory "$REPO_DIR" >/dev/null 2>&1 || true

git rev-parse --is-inside-work-tree >/dev/null

git checkout main >/dev/null 2>&1 || true
# Avoid merge commits
if git remote get-url origin >/dev/null 2>&1; then
  git fetch origin main >/dev/null 2>&1 || true
  git pull --ff-only origin main >/dev/null 2>&1 || true
fi

# ---- Project metadata ----
project_json="$(gh project view "$PROJECT_NUMBER" --owner "$OWNER" --format json)"
fields_json="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json)"

PROJECT_ID="$(
  printf '%s' "$project_json" | python3 -c 'import json,sys; obj=json.load(sys.stdin); print(obj.get("id") or "")'
)"

STATUS_FIELD_ID="$(
  printf '%s' "$fields_json" | python3 -c 'import json,sys
obj=json.load(sys.stdin)
for f in obj.get("fields", []):
  if f.get("name") == "Status":
    print(f.get("id") or "")
    break'
)"

if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: Could not resolve project id" >&2
  exit 1
fi
if [[ -z "$STATUS_FIELD_ID" ]]; then
  echo "ERROR: Could not resolve Status field id" >&2
  exit 1
fi

status_option_id() {
  local name="$1"
  printf '%s' "$fields_json" | python3 -c 'import json,sys
name=sys.argv[1]
obj=json.load(sys.stdin)
for f in obj.get("fields", []):
  if f.get("name") != "Status":
    continue
  for opt in f.get("options", []) or []:
    if opt.get("name") == name:
      print(opt.get("id") or "")
      raise SystemExit(0)
print("")
' "$name"
}

OPT_READY="$(status_option_id "Ready")"
OPT_IN_PROGRESS="$(status_option_id "In progress")"
OPT_IN_REVIEW="$(status_option_id "In review")"
OPT_BACKLOG="$(status_option_id "Backlog")"

for v in OPT_READY OPT_IN_PROGRESS OPT_IN_REVIEW OPT_BACKLOG; do
  if [[ -z "${!v}" ]]; then
    echo "ERROR: Could not resolve Status option id for ${v#OPT_}" >&2
    exit 1
  fi
done

move_status() {
  local item_id="$1"
  local option_id="$2"
  gh project item-edit \
    --id "$item_id" \
    --project-id "$PROJECT_ID" \
    --field-id "$STATUS_FIELD_ID" \
    --single-select-option-id "$option_id" \
    >/dev/null
}

pick_next_item() {
  # Always use: gh project item-list 1 --owner simonvanlaak --limit 200 --format json
  # The CLI returns: { items: [...], totalCount: N }
  gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 200 --format json \
  | python3 -c 'import json,sys
obj=json.load(sys.stdin)
items=obj.get("items") or []
for s in ("In progress", "Ready"):
  for it in items:
    if it.get("status") == s:
      print(json.dumps(it))
      raise SystemExit(0)
' || true
}

comment_issue() {
  local issue_ref="$1"
  local body="$2"
  gh issue comment "$issue_ref" --body "$body" >/dev/null
}

MAX_ITEMS_PER_RUN="${MAX_ITEMS_PER_RUN:-0}" # 0 = unlimited
items_done=0

while true; do
  if [[ "$MAX_ITEMS_PER_RUN" != "0" && "$items_done" -ge "$MAX_ITEMS_PER_RUN" ]]; then
    exit 0
  fi

  item_json="$(pick_next_item)"
  if [[ -z "$item_json" ]]; then
    exit 0
  fi

  item_id="$(printf '%s' "$item_json" | python3 -c 'import json,sys; obj=json.load(sys.stdin); print(obj.get("id") or "")')"
  item_status="$(printf '%s' "$item_json" | python3 -c 'import json,sys; obj=json.load(sys.stdin); print(obj.get("status") or "")')"
  issue_url="$(printf '%s' "$item_json" | python3 -c 'import json,sys; obj=json.load(sys.stdin); c=obj.get("content") or {}; print(c.get("url") or "")')"
  title="$(printf '%s' "$item_json" | python3 -c 'import json,sys; obj=json.load(sys.stdin); c=obj.get("content") or {}; print(c.get("title") or obj.get("title") or "")')"

  if [[ -z "$item_id" ]]; then
    echo "ERROR: Could not parse project item id" >&2
    exit 1
  fi
  if [[ -z "$issue_url" ]]; then
    echo "ERROR: Project item $item_id has no content.url (draft item?) — unsupported." >&2
    exit 1
  fi

  if [[ "$item_status" == "Ready" ]]; then
    move_status "$item_id" "$OPT_IN_PROGRESS"
    item_status="In progress"
  fi

  # Clean slate
  git reset --hard >/dev/null 2>&1 || true
  git clean -fd >/dev/null 2>&1 || true
  if git remote get-url origin >/dev/null 2>&1; then
    git fetch origin main >/dev/null 2>&1 || true
    git reset --hard origin/main >/dev/null 2>&1 || true
  fi

  export CYBERNETICAGENTS_ISSUE_URL="$issue_url"
  export CYBERNETICAGENTS_PROJECT_ITEM_ID="$item_id"

  # Run validation/work script before pushing code
  set +e
  bash ./scripts/nightly-cyberneticagents.sh
  rc=$?
  set -e

  if [[ $rc -ne 0 ]]; then
    move_status "$item_id" "$OPT_BACKLOG"
    comment_issue "$issue_url" "Blocked running automation (exit $rc).\n\nQuestions / next steps:\n- Please check the latest run logs and advise how to proceed.\n- If this should be handled manually, point me at the intended procedure.\n\nI moved this back to Backlog."
    echo "Moved to Backlog (blocked): $issue_url" >&2
    exit 0
  fi

  sha=""
  if ! git diff --quiet; then
    git add -A
    commit_msg="CyberneticAgents: ${title:-$issue_url}"
    git commit -m "$commit_msg" >/dev/null
    sha="$(git rev-parse HEAD)"
    git push origin main >/dev/null
  fi

  move_status "$item_id" "$OPT_IN_REVIEW"

  if [[ -n "$sha" ]]; then
    comment_issue "$issue_url" "Automation complete.\n\n- Project item: $item_id\n- Status: In review\n- Commit: $sha\n\nValidation: ran ./scripts/nightly-cyberneticagents.sh"
  else
    comment_issue "$issue_url" "Automation complete (no code changes).\n\n- Project item: $item_id\n- Status: In review\n\nValidation: ran ./scripts/nightly-cyberneticagents.sh"
  fi

  items_done=$((items_done + 1))
done
