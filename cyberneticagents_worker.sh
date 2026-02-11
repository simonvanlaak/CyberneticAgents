#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/node/.local/bin:$PATH"

# Non-interactive auth ------------------------------------------------
if [[ -z "${GH_TOKEN:-}" ]]; then
  export GH_TOKEN="$(op item get "GitHub Personal Access Token" --vault OpenClaw --fields token --reveal 2>/dev/null || true)"
fi
if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "GH_TOKEN missing (op lookup failed)" >&2
  exit 1
fi

gh auth status -h github.com >/dev/null 2>&1

cd /root/.openclaw/workspace
[[ -d CyberneticAgents ]] && cd CyberneticAgents

PROJECT_OWNER="simonvanlaak"
PROJECT_NUMBER="1"

# Helpers -------------------------------------------------------------

get_items_json() {
  gh project item-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --limit 200 --format json
}

# Print: <project_item_id>\t<status>\t<content_url>\n
pick_next_item_tsv() {
  local json_input="$1"
  python3 -c 'import json,sys

data=json.loads(sys.argv[1])
items=data.get("items",[])

def get_status(it):
    fv=it.get("fieldValues") or {}
    s=fv.get("Status") or fv.get("status")
    if isinstance(s,dict):
        return s.get("name") or ""
    if isinstance(s,str):
        return s
    # Sometimes fieldValues is a list of {field:{name}, value:{...}}
    if isinstance(fv,list):
        for x in fv:
            field=(x.get("field") or {})
            if field.get("name")=="Status":
                v=x.get("value")
                if isinstance(v,dict):
                    return v.get("name") or v.get("title") or ""
                return v or ""
    return ""

def get_id(it):
    return it.get("id") or it.get("itemId") or it.get("nodeId") or ""

def get_url(it):
    c=it.get("content") or {}
    return c.get("url") or it.get("contentUrl") or ""

pref=["Ready"]
for want in pref:
    for it in items:
        if get_status(it)==want:
            print(f"{get_id(it)}\t{want}\t{get_url(it)}")
            sys.exit(0)

sys.exit(1)
' "$json_input"
}

# Project mutations ---------------------------------------------------

set_item_status() {
  local item_id="$1"; shift
  local new_status="$1"; shift

  if gh project item-edit "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --id "$item_id" --field "Status" --value "$new_status" >/dev/null 2>&1; then
    return 0
  fi
  if gh project item-edit "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --item-id "$item_id" --field "Status" --value "$new_status" >/dev/null 2>&1; then
    return 0
  fi

  echo "Failed to set Status=$new_status for project item $item_id" >&2
  return 1
}

comment_on_content() {
  local content_url="$1"; shift
  local body="$1"; shift

  [[ -n "$content_url" ]] || return 0

  if [[ "$content_url" == *"/pull/"* ]]; then
    gh pr comment "$content_url" --body "$body" >/dev/null
  else
    gh issue comment "$content_url" --body "$body" >/dev/null
  fi
}

run_nightly_script() {
  if [[ -f ./scripts/nightly-cyberneticagents.sh ]]; then
    bash ./scripts/nightly-cyberneticagents.sh
  else
    echo "Missing ./scripts/nightly-cyberneticagents.sh" >&2
    return 1
  fi
}

# Work loop -----------------------------------------------------------

while true; do
  items_json=$(get_items_json)

  if ! line=$(pick_next_item_tsv "$items_json"); then
    # No items Ready/In progress
    exit 0
  fi

  IFS=$'\t' read -r project_item_id status content_url <<<"$line"

  if [[ -z "$project_item_id" ]]; then
    echo "Could not determine project item id" >&2
    exit 1
  fi

  if [[ "$status" == "Ready" ]]; then
    set_item_status "$project_item_id" "In progress"
    comment_on_content "$content_url" "Picked up from Ready → In progress. Running nightly automation now."
  fi

  # Main-only workflow: update main, run validation, commit/push.
  git fetch origin main >/dev/null 2>&1 || true
  git checkout main >/dev/null 2>&1 || true
  git pull --ff-only origin main >/dev/null 2>&1 || true

  if ! run_nightly_script; then
    echo "nightly script failed for project item $project_item_id ($content_url)" >&2
    exit 1
  fi

  if ! git diff --quiet; then
    git add -A
    if ! git diff --cached --quiet; then
      git commit -m "CyberneticAgents nightly automation" >/dev/null
      git push origin main >/dev/null
    fi
  fi

  sha=$(git rev-parse HEAD)

  set_item_status "$project_item_id" "In review"
  comment_on_content "$content_url" "Moved to In review.\n\nSummary: ran nightly automation and pushed to main.\nValidation: bash ./scripts/nightly-cyberneticagents.sh\nCommit: $sha"

done
