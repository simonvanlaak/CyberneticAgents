#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/node/.local/bin:$PATH"

# --- Auth (non-interactive) ---
if [[ -z "${GH_TOKEN:-}" ]]; then
  if command -v op >/dev/null 2>&1; then
    # Do NOT print the token.
    GH_TOKEN="$(op item get 'GitHub Personal Access Token' --vault OpenClaw --fields token --reveal 2>/dev/null || true)"
    export GH_TOKEN
  fi
fi

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "GH_TOKEN is empty and could not be loaded from 1Password (op missing or item unavailable)." >&2
  exit 2
fi

if ! gh auth status -h github.com >/dev/null 2>&1; then
  echo "gh is not authenticated for github.com (GH_TOKEN invalid/missing scopes?)." >&2
  exit 3
fi

cd /root/.openclaw/workspace

die_unexpected() {
  echo "$1" >&2
  exit 10
}

pick_item_tsv() {
  local json="$1"
  jq -r '
    def status: (.fields[]? | select(.name=="Status") | (.value // .text // .name // .)) // "";
    def url: (.content.url // .contentUrl // .content_url // "");
    def ctype: (.content.type // .contentType // .content_type // "");
    def title: (.content.title // .title // "");

    [ .items[]? | {id, st: status, u: url, ct: ctype, t: title} ]
    | (map(select(.st=="In progress")) | .[0])
      // (map(select(.st=="Ready")) | .[0])
    | if .==null then empty else [.id,.st,.u,.ct,.t] | @tsv end
  ' <<<"$json" 2>/dev/null || true
}

move_status() {
  local item_id="$1" to="$2"

  # gh versions differ; try a couple of common spellings.
  gh project item-edit 1 --owner simonvanlaak --id "$item_id" --field "Status" --value "$to" >/dev/null 2>&1 \
    || gh project item-edit 1 --owner simonvanlaak --id "$item_id" --field-name "Status" --field-value "$to" >/dev/null 2>&1
}

comment_issue() {
  local url="$1" body="$2"

  # Best-effort: comment by URL.
  gh issue comment "$url" --body "$body" >/dev/null 2>&1 || true
}

ensure_main_clean() {
  git fetch origin main >/dev/null 2>&1 || true
  git checkout -q main
  git pull --ff-only origin main >/dev/null
}

run_nightly() {
  bash ./scripts/nightly-cyberneticagents.sh
}

maybe_commit_push() {
  if git diff --quiet && git diff --cached --quiet; then
    echo "No code changes to commit."
    return 0
  fi

  git add -A
  local sha_before sha_after
  sha_before="$(git rev-parse --short HEAD)"
  git commit -m "Nightly automation" >/dev/null
  git push origin main >/dev/null
  sha_after="$(git rev-parse --short HEAD)"
  echo "Pushed commit ${sha_after} (from ${sha_before})."
}

# --- Work loop ---
while true; do
  items_json="$(gh project item-list 1 --owner simonvanlaak --limit 200 --format json)"
  picked="$(pick_item_tsv "$items_json")"

  if [[ -z "$picked" ]]; then
    exit 0
  fi

  IFS=$'\t' read -r item_id status content_url content_type title <<<"$picked"

  if [[ "$status" == "Ready" ]]; then
    move_status "$item_id" "In progress" || die_unexpected "Failed to move project item $item_id Ready→In progress"
    status="In progress"
  fi

  if [[ -z "${content_url:-}" ]]; then
    move_status "$item_id" "Backlog" || true
    comment_issue "$content_url" "Moved to Backlog: I could not determine the linked issue/PR URL from the project item payload.\n\nQuestions:\n- What issue/PR does this item correspond to?\n- Is there a preferred repo/path for this work?"
    exit 0
  fi

  ensure_main_clean

  if ! run_nightly; then
    move_status "$item_id" "Backlog" || true
    comment_issue "$content_url" "Moved to Backlog: nightly automation script failed (./scripts/nightly-cyberneticagents.sh).\n\nQuestions:\n- Is this item expected to be handled by the nightly automation?\n- Any recent dependency/env changes needed?"
    exit 5
  fi

  commit_info="$(maybe_commit_push)"

  move_status "$item_id" "In review" || die_unexpected "Failed to move project item $item_id In progress→In review"

  comment_issue "$content_url" "Moved to In review.\n\nSummary:\n- Ran: ./scripts/nightly-cyberneticagents.sh\n- ${commit_info}\n\nValidation:\n- Script exited successfully."

done
