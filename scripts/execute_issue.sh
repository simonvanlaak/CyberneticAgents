#!/usr/bin/env bash
set -euo pipefail

# Execute one GitHub issue in-place on main.
#
# This script is intentionally a *framework*:
# - It enforces preconditions (clean tree, synced main, auth present)
# - It fetches and stores the issue context locally
# - It delegates actual implementation to an optional handler script
#
# Policy:
# - Work happens on main (no branch switching)
# - Create multiple atomic commits during work (NOT in this script)
# - Push only once at the end (handled by the caller/worker)

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <repo> <issue_number>" >&2
  exit 2
fi

REPO="$1"           # e.g. simonvanlaak/CyberneticAgents
ISSUE_NUMBER="$2"   # e.g. 97

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! git diff --quiet; then
  echo "ERROR: working tree has uncommitted changes" >&2
  exit 3
fi

# Sync baseline
git fetch origin main >/dev/null 2>&1 || true
git checkout main >/dev/null 2>&1 || true
git pull --rebase origin main >/dev/null

# Capture issue context for the agent/human.
mkdir -p .tmp/issues
ISSUE_JSON_PATH=".tmp/issues/${ISSUE_NUMBER}.json"
ISSUE_MD_PATH=".tmp/issues/${ISSUE_NUMBER}.md"

gh api "repos/${REPO}/issues/${ISSUE_NUMBER}" >"$ISSUE_JSON_PATH"

python3 - <<'PY' "$ISSUE_JSON_PATH" "$ISSUE_MD_PATH"
import json,sys
src=sys.argv[1]
dst=sys.argv[2]
data=json.load(open(src,'r',encoding='utf-8'))
labels=[l['name'] for l in data.get('labels',[])]
body=data.get('body') or ''
with open(dst,'w',encoding='utf-8') as f:
    f.write(f"# Issue #{data['number']}: {data['title']}\n\n")
    f.write(f"URL: {data.get('html_url','')}\n")
    f.write(f"Labels: {', '.join(labels)}\n\n")
    f.write(body.strip()+"\n")
PY

# Delegate to an optional per-issue handler.
HANDLER="./scripts/issue_handlers/${ISSUE_NUMBER}.sh"
if [[ -x "$HANDLER" ]]; then
  "$HANDLER" "$REPO" "$ISSUE_NUMBER"
  exit 0
fi

# No handler exists yet.
# The caller (LLM agent) should implement the issue directly and create atomic commits.
echo "NO_HANDLER: wrote issue context to $ISSUE_MD_PATH" >&2
exit 4
