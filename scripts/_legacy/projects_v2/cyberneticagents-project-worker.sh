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

cd /root/.openclaw/workspace/CyberneticAgents

die_unexpected() {
  echo "$1" >&2
  exit 10
}

pick_item_tsv() {
  local json="$1"

  # Prefer python3 (available on the runner) to avoid jq dependency.
  python3 - "$json" <<'PY' 2>/dev/null || true
import json, sys

raw = sys.argv[1] if len(sys.argv) > 1 else ""
if not raw.strip():
    sys.exit(0)

try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)

items = data.get('items') if isinstance(data, dict) else None
if items is None and isinstance(data, list):
    items = data
if not isinstance(items, list):
    sys.exit(0)

def get_status(it):
    fields = it.get('fields') or []
    if isinstance(fields, dict):
        fields = [fields]
    for f in fields:
        if not isinstance(f, dict):
            continue
        if f.get('name') == 'Status':
            v = f.get('value')
            if isinstance(v, dict):
                v = v.get('name') or v.get('text')
            return (v or f.get('text') or f.get('fieldValue') or '').strip()
    return ''

def get_content_url(it):
    c = it.get('content') or {}
    if not isinstance(c, dict):
        c = {}
    return (c.get('url') or it.get('contentUrl') or it.get('content_url') or '').strip()

def get_content_type(it):
    c = it.get('content') or {}
    if not isinstance(c, dict):
        c = {}
    return (c.get('type') or it.get('contentType') or it.get('content_type') or '').strip()

def get_title(it):
    c = it.get('content') or {}
    if not isinstance(c, dict):
        c = {}
    return (c.get('title') or it.get('title') or '').strip()

cands = []
for it in items:
    if not isinstance(it, dict):
        continue
    item_id = (it.get('id') or '').strip()
    if not item_id:
        continue
    st = get_status(it)
    cands.append({
        'id': item_id,
        'st': st,
        'u': get_content_url(it),
        'ct': get_content_type(it),
        't': get_title(it),
    })

pick = None
for st_pref in ('In progress', 'Ready'):
    for c in cands:
        if c.get('st') == st_pref:
            pick = c
            break
    if pick:
        break

if not pick:
    sys.exit(0)

def tsv_escape(s):
    return (s or '').replace('\t',' ').replace('\n',' ').replace('\r',' ')

print('\t'.join([tsv_escape(pick.get('id')), tsv_escape(pick.get('st')), tsv_escape(pick.get('u')), tsv_escape(pick.get('ct')), tsv_escape(pick.get('t'))]))
PY
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

  if [[ -z "${content_url:-}" ]]; then
    move_status "$item_id" "Backlog" || true
    comment_issue "$content_url" "Moved to Backlog: I could not determine the linked issue/PR URL from the project item payload.\n\nQuestions:\n- What issue/PR does this item correspond to?\n- Is there a preferred repo/path for this work?"
    exit 0
  fi

  # If an item is "Ready" but the linked issue doesn't describe a clear, executable change,
  # move it to Backlog and ask for clarification instead of burning cycles.
  issue_body="$(gh issue view "$content_url" --json body --jq .body 2>/dev/null || true)"
  if [[ "$status" == "Ready" ]]; then
    if [[ -z "${issue_body//[[:space:]]/}" ]]; then
      move_status "$item_id" "Blocked" || true
      comment_issue "$content_url" $'Moved to Blocked: issue body is empty / missing requirements (cannot be solved by the agent alone).\n\nPlease add:\n- Expected outcome\n- Acceptance criteria\n- Any constraints/links (docs, PRDs, etc.)'
      exit 0
    fi

    # Common anti-pattern: ticket body is *only* a docs path. That’s not actionable for automation.
    if echo "$issue_body" | tr -d '\r' | grep -Eq '^[[:space:]]*docs/[^[:space:]]+\.md[[:space:]]*$'; then
      move_status "$item_id" "Blocked" || true
      comment_issue "$content_url" $'Moved to Blocked: issue body only links a doc path (not an actionable spec; cannot be solved by the agent alone).\n\nPlease paste the relevant doc content into the issue (or summarize requirements + acceptance criteria), then move it back to Ready.'
      exit 0
    fi

    move_status "$item_id" "In progress" || die_unexpected "Failed to move project item $item_id Ready→In progress"
    status="In progress"
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
