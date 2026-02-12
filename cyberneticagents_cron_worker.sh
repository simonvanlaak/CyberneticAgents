#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/root/.openclaw/workspace/CyberneticAgents"
cd "$REPO_DIR"

export PATH="/home/node/.local/bin:$PATH"

if [ -z "${GH_TOKEN:-}" ]; then
  command -v tmux >/dev/null || { echo "tmux is required for 1Password CLI auth" >&2; exit 1; }

  TMP_TOKEN_FILE="$(mktemp)"
  SOCKET_DIR="${CLAWDBOT_TMUX_SOCKET_DIR:-${TMPDIR:-/tmp}/clawdbot-tmux-sockets}"
  mkdir -p "$SOCKET_DIR"
  SOCKET="$SOCKET_DIR/clawdbot-op.sock"
  SESSION="op-auth-$(date +%Y%m%d-%H%M%S)-$$"

  # Run op inside tmux to avoid repeated auth prompts in non-interactive shells.
  tmux -S "$SOCKET" new -d -s "$SESSION" "bash -lc \"op item get 'GitHub Personal Access Token' --vault OpenClaw --fields token --reveal 2>/dev/null >'$TMP_TOKEN_FILE' || true\""

  # Wait for the command to finish (session exits when command ends).
  for _ in $(seq 1 100); do
    if ! tmux -S "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done
  tmux -S "$SOCKET" kill-session -t "$SESSION" >/dev/null 2>&1 || true

  export GH_TOKEN="$(cat "$TMP_TOKEN_FILE" 2>/dev/null || true)"
  rm -f "$TMP_TOKEN_FILE"
fi

if [ -z "${GH_TOKEN:-}" ]; then
  echo "GH_TOKEN unavailable (1Password lookup failed)." >&2
  exit 1
fi

gh auth status -h github.com >/dev/null
command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }

OWNER="simonvanlaak"
PROJECT=1

get_items_json(){
  gh project item-list "$PROJECT" --owner "$OWNER" --limit 200 --format json
}

# NOTE: `gh project item-list ... --format json` has changed schema across gh versions.
# We try a few common shapes.
_items_array(){
  jq -c '(.items // .data.items // .) // []'
}

pick_item_id_by_status(){
  local status="$1"
  _items_array | jq -r --arg st "$status" 'map(select((.status // .Status // .fields.Status // .["Status"] // "") == $st)) | .[0] | (.id // .itemId // .["id"] // "")'
}

item_issue_url(){
  local itemId="$1"
  _items_array | jq -r --arg id "$itemId" 'map(select((.id // .itemId // .["id"]) == $id)) | .[0] | (.content.url // .contentUrl // .content.url // .url // "")'
}

# Resolve ProjectV2 IDs needed for item-edit (project-id, field-id, option-id)
_project_ids_json(){
  gh project view "$PROJECT" --owner "$OWNER" --format json
}

# Emits: <project_id>\t<status_field_id>\t<option_id>\n
_status_option_id(){
  local status_name="$1"
  python3 - <<'PY'
import json,sys
status_name=sys.argv[1]
data=json.load(sys.stdin)
project_id=data.get('id') or ''
fields=data.get('fields') or []
status_field=None
for f in fields:
    if (f.get('name') or '')=='Status':
        status_field=f
        break
if not status_field:
    print("\t\t")
    sys.exit(0)
field_id=status_field.get('id') or ''
opt_id=''
for opt in (status_field.get('options') or []):
    if (opt.get('name') or '')==status_name:
        opt_id=opt.get('id') or ''
        break
print(f"{project_id}\t{field_id}\t{opt_id}")
PY
}

move_item(){
  local itemId="$1" newStatus="$2"

  local ids_json project_id field_id option_id
  ids_json=$(_project_ids_json)
  IFS=$'\t' read -r project_id field_id option_id < <(echo "$ids_json" | _status_option_id "$newStatus")

  if [ -z "${project_id:-}" ] || [ -z "${field_id:-}" ] || [ -z "${option_id:-}" ]; then
    echo "Unable to resolve Project/Status IDs for move to '$newStatus'" >&2
    return 1
  fi

  gh project item-edit --id "$itemId" --field-id "$field_id" --project-id "$project_id" --single-select-option-id "$option_id" >/dev/null
}

comment_on_issue(){
  local issueUrl="$1" body="$2"
  local nwo num
  nwo=$(echo "$issueUrl" | sed -nE 's#https://github.com/([^/]+/[^/]+)/issues/([0-9]+).*#\1#p')
  num=$(echo "$issueUrl" | sed -nE 's#https://github.com/([^/]+/[^/]+)/issues/([0-9]+).*#\2#p')
  if [ -n "$nwo" ] && [ -n "$num" ]; then
    gh issue comment "$num" -R "$nwo" -b "$body" >/dev/null
  fi
}

ensure_clean_main(){
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Not in a git repo" >&2; exit 1; }
  git fetch origin main >/dev/null 2>&1 || true
  git checkout main >/dev/null 2>&1 || true
  git pull --ff-only origin main >/dev/null 2>&1 || true
}

run_nightly(){
  bash ./scripts/nightly-cyberneticagents.sh
}

MAX_ITEMS="${MAX_ITEMS:-3}"
PROCESSED=0

while true; do
  ITEMS_JSON=$(get_items_json)

  # Work selection loop:
  # 1) Prefer top-most Status=="In progress"
  # 2) Else pick top-most Status=="Ready"
  ITEM_ID=$(echo "$ITEMS_JSON" | pick_item_id_by_status "In progress")
  PICKED_STATUS="In progress"

  if [ -z "$ITEM_ID" ] || [ "$ITEM_ID" = "null" ]; then
    ITEM_ID=$(echo "$ITEMS_JSON" | pick_item_id_by_status "Ready")
    PICKED_STATUS="Ready"
  fi

  if [ -z "$ITEM_ID" ] || [ "$ITEM_ID" = "null" ]; then
    exit 0
  fi

  ISSUE_URL=$(echo "$ITEMS_JSON" | item_issue_url "$ITEM_ID" || true)

  if [ "$PICKED_STATUS" = "Ready" ]; then
    move_item "$ITEM_ID" "In progress"
  fi

  ensure_clean_main

  set +e
  run_nightly
  RC=$?
  set -e

  if [ $RC -ne 0 ]; then
    move_item "$ITEM_ID" "Backlog"

    if [ -n "${ISSUE_URL:-}" ] && [ "${ISSUE_URL:-}" != "null" ]; then
      comment_on_issue "$ISSUE_URL" "Blocked while running nightly CyberneticAgents automation (exit $RC).\n\nQuestions:\n- What should be the expected behavior/output for this item?\n- Any specific steps to reproduce or acceptance criteria?\n"
    fi

    echo "Unexpected failure for item $ITEM_ID (rc=$RC)." >&2
    continue
  fi

  SHA=""
  if ! git diff --quiet || ! git diff --cached --quiet; then
    git add -A
    if ! git diff --cached --quiet; then
      git commit -m "nightly: CyberneticAgents usability + auto-fix" >/dev/null
      SHA=$(git rev-parse HEAD)
      git push origin main >/dev/null
    fi
  fi

  move_item "$ITEM_ID" "In review"

  if [ -n "${ISSUE_URL:-}" ] && [ "${ISSUE_URL:-}" != "null" ]; then
    comment_on_issue "$ISSUE_URL" "Moved to **In review** after nightly CyberneticAgents automation.\n\nValidation:\n- Ran `bash ./scripts/nightly-cyberneticagents.sh` (success).\n\nCommits:\n- ${SHA:-No code changes}"
  fi

  PROCESSED=$((PROCESSED+1))
  if [ "$PROCESSED" -ge "$MAX_ITEMS" ]; then
    exit 0
  fi

done
