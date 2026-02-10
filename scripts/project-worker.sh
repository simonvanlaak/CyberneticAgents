#!/usr/bin/env bash
set -euo pipefail

# CyberneticAgents GitHub Project worker
# - Processes items in Project #1 (owner: simonvanlaak)
# - Prefers Status=="In progress", else Status=="Ready"
# - Moves Ready -> In progress immediately
# - When complete: In progress -> In review
# - When blocked: move to Backlog + leave explicit questions

OWNER="simonvanlaak"
PROJECT_NUMBER="1"

export PATH="/home/node/.local/bin:$PATH"

# ---- Auth (non-interactive) ----
if [[ -z "${GH_TOKEN:-}" ]]; then
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
REPO_DIR="/root/.openclaw/workspace/CyberneticAgents"
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
PROJECT_ID="$(jq -r '.id' <<<"$project_json")"

fields_json="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json)"
STATUS_FIELD_ID="$(jq -r '.fields[] | select(.name=="Status") | .id' <<<"$fields_json")"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "null" ]]; then
  echo "ERROR: Could not resolve project id" >&2
  exit 1
fi
if [[ -z "$STATUS_FIELD_ID" || "$STATUS_FIELD_ID" == "null" ]]; then
  echo "ERROR: Could not resolve Status field id" >&2
  exit 1
fi

status_option_id() {
  local name="$1"
  jq -r --arg n "$name" '.fields[]
    | select(.name=="Status")
    | .options[]
    | select(.name==$n)
    | .id' <<<"$fields_json"
}

OPT_READY="$(status_option_id "Ready")"
OPT_IN_PROGRESS="$(status_option_id "In progress")"
OPT_IN_REVIEW="$(status_option_id "In review")"
OPT_BACKLOG="$(status_option_id "Backlog")"

for v in OPT_READY OPT_IN_PROGRESS OPT_IN_REVIEW OPT_BACKLOG; do
  if [[ -z "${!v}" || "${!v}" == "null" ]]; then
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
  # We treat array order as the "top-most" order.
  gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 200 --format json \
  | jq -c '
      .items
      | (map(select(.status=="In progress")) | .[0])
        // (map(select(.status=="Ready")) | .[0])
        // empty
    '
}

comment_issue() {
  local issue_ref="$1"; shift
  local body="$*"
  gh issue comment "$issue_ref" --body "$body" >/dev/null
}

MAX_ITEMS_PER_RUN="${MAX_ITEMS_PER_RUN:-0}" # 0 = unlimited
items_done=0

while true; do
  if [[ "$MAX_ITEMS_PER_RUN" != "0" && "$items_done" -ge "$MAX_ITEMS_PER_RUN" ]]; then
    exit 0
  fi

  item_json="$(pick_next_item || true)"
  if [[ -z "$item_json" ]]; then
    exit 0
  fi

  item_id="$(jq -r '.id' <<<"$item_json")"
  item_status="$(jq -r '.status' <<<"$item_json")"
  issue_url="$(jq -r '.content.url // empty' <<<"$item_json")"
  title="$(jq -r '.content.title // .title // ""' <<<"$item_json")"

  if [[ -z "$item_id" || "$item_id" == "null" ]]; then
    echo "ERROR: Could not parse project item id" >&2
    exit 1
  fi
  if [[ -z "$issue_url" || "$issue_url" == "null" ]]; then
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
