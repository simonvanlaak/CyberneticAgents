#!/usr/bin/env bash
set -euo pipefail

# If the latest GitLab CI pipeline is failing, open (or update) a GitHub issue with
# the failure details and move it to the top of the "Ready" column in GitHub
# Project #1.
#
# This is intentionally safe-by-default:
# - If required env vars are missing, it logs and exits 0.
# - It avoids duplicate issue spam by searching for an existing open issue keyed
#   by the pipeline ID.
#
# Required env vars:
#   GITLAB_PROJECT_ID   (numeric ID or URL-encoded path, e.g. 12345 or group%2Frepo)
#   GITLAB_TOKEN        (personal or project access token with API read access)
# Optional:
#   GITLAB_BASE_URL     (default: https://gitlab.com)
#   GITLAB_REF          (branch/ref to check; default: main)
#   GITLAB_PER_PAGE     (default: 1)
#
# GitHub/Project configuration (defaults to this repo + Simon's user project):
#   GH_REPO             (default: simonvanlaak/CyberneticAgents)
#   GH_PROJECT_OWNER    (default: simonvanlaak)
#   GH_PROJECT_NUMBER   (default: 1)
#
# Notes:
# - This script uses `gh` (GitHub CLI) and `python3` for JSON parsing.

log() { echo "[gitlab-ci-watch] $*"; }

GITLAB_BASE_URL="${GITLAB_BASE_URL:-https://gitlab.com}"
GITLAB_PROJECT_ID="${GITLAB_PROJECT_ID:-}"
GITLAB_TOKEN="${GITLAB_TOKEN:-}"
GITLAB_REF="${GITLAB_REF:-main}"
GITLAB_PER_PAGE="${GITLAB_PER_PAGE:-1}"

GH_REPO="${GH_REPO:-simonvanlaak/CyberneticAgents}"
GH_PROJECT_OWNER="${GH_PROJECT_OWNER:-simonvanlaak}"
GH_PROJECT_NUMBER="${GH_PROJECT_NUMBER:-1}"

if [ -z "$GITLAB_PROJECT_ID" ] || [ -z "$GITLAB_TOKEN" ]; then
  log "GITLAB_PROJECT_ID/GITLAB_TOKEN not set; skipping"
  exit 0
fi

command -v curl >/dev/null 2>&1 || { log "curl not found"; exit 2; }
command -v python3 >/dev/null 2>&1 || { log "python3 not found"; exit 2; }

if ! command -v gh >/dev/null 2>&1; then
  log "gh not found; skipping"
  exit 0
fi

# Non-interactive auth check (GH_TOKEN should already be exported by the caller)
if ! gh auth status -h github.com >/dev/null 2>&1; then
  log "gh not authenticated (non-interactive); skipping"
  exit 0
fi

api() {
  local url="$1"; shift
  curl -fsSL \
    -H "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
    "$url" "$@"
}

pipelines_json="$(api "${GITLAB_BASE_URL}/api/v4/projects/${GITLAB_PROJECT_ID}/pipelines?ref=${GITLAB_REF}&per_page=${GITLAB_PER_PAGE}")"

latest="$(printf "%s" "$pipelines_json" | python3 - <<'PY'
import json,sys
pipelines=json.load(sys.stdin)
if not pipelines:
  sys.exit(0)
print(json.dumps(pipelines[0]))
PY
)" || true

if [ -z "$latest" ]; then
  log "no pipelines found for ref=${GITLAB_REF}; skipping"
  exit 0
fi

status="$(printf "%s" "$latest" | python3 - <<'PY'
import json,sys
p=json.load(sys.stdin)
print(p.get('status',''))
PY
)"

if [ "$status" != "failed" ]; then
  log "latest pipeline status=${status}; nothing to do"
  exit 0
fi

pipeline_id="$(printf "%s" "$latest" | python3 - <<'PY'
import json,sys
p=json.load(sys.stdin)
print(p.get('id',''))
PY
)"
sha="$(printf "%s" "$latest" | python3 - <<'PY'
import json,sys
p=json.load(sys.stdin)
print(p.get('sha',''))
PY
)"
web_url="$(printf "%s" "$latest" | python3 - <<'PY'
import json,sys
p=json.load(sys.stdin)
print(p.get('web_url',''))
PY
)"

if [ -z "$pipeline_id" ]; then
  log "could not parse pipeline id; aborting"
  exit 2
fi

key="GitLab pipeline ${pipeline_id}"

existing_url="$(gh issue list --repo "$GH_REPO" --state open --search "$key in:title" --json url --limit 5 2>/dev/null | python3 - <<'PY'
import json,sys
issues=json.load(sys.stdin)
print(issues[0]['url'] if issues else '')
PY
)" || true

failed_jobs_json="$(api "${GITLAB_BASE_URL}/api/v4/projects/${GITLAB_PROJECT_ID}/pipelines/${pipeline_id}/jobs?scope[]=failed")"

jobs_summary="$(printf "%s" "$failed_jobs_json" | python3 - <<'PY'
import json,sys
jobs=json.load(sys.stdin)
lines=[]
for j in jobs[:10]:
  lines.append(f"- {j.get('name')} (stage: {j.get('stage')}, id: {j.get('id')})")
print("\n".join(lines))
PY
)"

# Pull a small trace snippet for the first failed job, if any.
trace_snip=""
first_job_id="$(printf "%s" "$failed_jobs_json" | python3 - <<'PY'
import json,sys
jobs=json.load(sys.stdin)
print(jobs[0].get('id','') if jobs else '')
PY
)" || true

if [ -n "$first_job_id" ]; then
  trace_snip="$(api "${GITLAB_BASE_URL}/api/v4/projects/${GITLAB_PROJECT_ID}/jobs/${first_job_id}/trace" | tail -n 120 | sed -e 's/\r$//' )" || true
fi

body_file="$(mktemp)"
trap 'rm -f "$body_file"' EXIT

cat >"$body_file" <<EOF
GitLab CI is failing.

- ${key}
- Ref: ${GITLAB_REF}
- SHA: ${sha}
- Pipeline URL: ${web_url}

## Failed jobs (top 10)
${jobs_summary:-"(no failed jobs returned)"}

## Trace snippet (last ~120 lines of first failed job)
\`\`\`
${trace_snip:-"(no trace available)"}
\`\`\`

## What to do
- Re-run the failing job(s) in GitLab (if transient) and/or fix the underlying test/build failure.
- When fixed, ensure the pipeline turns green on ${GITLAB_REF}.
EOF

issue_url=""
if [ -n "$existing_url" ]; then
  log "existing open issue found: $existing_url"
  issue_url="$existing_url"
else
  title="CI: fix failing GitLab pipeline (${pipeline_id})"
  log "creating GitHub issue: $title"
  issue_url="$(gh issue create --repo "$GH_REPO" --title "$title" --body-file "$body_file" 2>/dev/null)"
fi

if [ -z "$issue_url" ]; then
  log "could not create/find issue url; aborting"
  exit 2
fi

# Add to project (idempotent-ish; if already added this is fine).
item_id="$(gh project item-add "$GH_PROJECT_NUMBER" --owner "$GH_PROJECT_OWNER" --url "$issue_url" --format json 2>/dev/null | python3 - <<'PY'
import json,sys
obj=json.load(sys.stdin)
print(obj.get('id',''))
PY
)" || true

# If the item already existed, item-add may return empty. Try to locate it.
if [ -z "$item_id" ]; then
  item_id="$(gh project item-list "$GH_PROJECT_NUMBER" --owner "$GH_PROJECT_OWNER" --limit 200 --format json 2>/dev/null | python3 - <<'PY'
import json,sys
items=json.load(sys.stdin).get('items',[])
url=sys.argv[1]
for it in items:
  c=it.get('content') or {}
  if c.get('url')==url:
    print(it.get('id',''))
    break
PY
"$issue_url")" || true
fi

if [ -z "$item_id" ]; then
  log "could not find project item id; done (issue created but not added to project?)"
  exit 0
fi

project_id="$(gh project view "$GH_PROJECT_NUMBER" --owner "$GH_PROJECT_OWNER" --format json 2>/dev/null | python3 - <<'PY'
import json,sys
p=json.load(sys.stdin)
print(p.get('id',''))
PY
)"

status_field_id="$(gh project field-list "$GH_PROJECT_NUMBER" --owner "$GH_PROJECT_OWNER" --format json 2>/dev/null | python3 - <<'PY'
import json,sys
fields=json.load(sys.stdin).get('fields',[])
for f in fields:
  if f.get('name')=='Status':
    print(f.get('id',''))
    break
PY
)"

ready_option_id="$(gh project field-list "$GH_PROJECT_NUMBER" --owner "$GH_PROJECT_OWNER" --format json 2>/dev/null | python3 - <<'PY'
import json,sys
fields=json.load(sys.stdin).get('fields',[])
for f in fields:
  if f.get('name')=='Status':
    for opt in f.get('options',[]):
      if opt.get('name')=='Ready':
        print(opt.get('id',''))
        raise SystemExit
PY
)"

if [ -n "$project_id" ] && [ -n "$status_field_id" ] && [ -n "$ready_option_id" ]; then
  log "setting project Status=Ready"
  gh project item-edit \
    --id "$item_id" \
    --project-id "$project_id" \
    --field-id "$status_field_id" \
    --single-select-option-id "$ready_option_id" \
    >/dev/null
fi

# Best-effort: move item to the top of the project (or at least near the top).
# GitHub exposes a dedicated mutation for item positioning.
log "attempting to move item to top of project"
gh api graphql -f query='mutation($projectId:ID!, $itemId:ID!){ updateProjectV2ItemPosition(input:{projectId:$projectId, itemId:$itemId}){ clientMutationId } }' \
  -f projectId="$project_id" -f itemId="$item_id" >/dev/null 2>&1 || true

log "done: $issue_url"
