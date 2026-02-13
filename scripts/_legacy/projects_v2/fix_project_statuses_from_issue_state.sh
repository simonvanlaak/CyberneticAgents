#!/usr/bin/env bash
set -euo pipefail

# Restores GitHub Project #1 Status for all items based on linked issue state.
# - CLOSED issues => Done
# - OPEN issues   => Ready
# Useful when status values were cleared by a Status field option update.

OWNER="@me"
PROJECT_NUMBER=1
REPO="simonvanlaak/CyberneticAgents"

PROJECT_ID="$(gh project view "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.id')"
STATUS_FIELD_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .id')"
READY_OPTION_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .options[] | select(.name=="Ready") | .id')"
DONE_OPTION_ID="$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --jq '.fields[] | select(.name=="Status") | .options[] | select(.name=="Done") | .id')"

ITEMS_JSON="$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --limit 200 --format json)"
ISSUES_JSON="$(gh issue list --repo "$REPO" --state all --limit 200 --json number,state)"

python3 - <<PY
import json, subprocess
items=json.loads('''$ITEMS_JSON''')['items']
issues=json.loads('''$ISSUES_JSON''')
state_by_num={i['number']: i['state'] for i in issues}
project_id='''$PROJECT_ID'''.strip()
field_id='''$STATUS_FIELD_ID'''.strip()
ready='''$READY_OPTION_ID'''.strip()
done='''$DONE_OPTION_ID'''.strip()

set_ready=set_done=0
for it in items:
    num=(it.get('content') or {}).get('number')
    if not num:
        continue
    target = done if state_by_num.get(num)=='CLOSED' else ready
    subprocess.check_call([
        'gh','project','item-edit',
        '--id',it['id'],
        '--project-id',project_id,
        '--field-id',field_id,
        '--single-select-option-id',target,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if target==done:
        set_done+=1
    else:
        set_ready+=1
print(f"Updated: Ready={set_ready} Done={set_done} Total={set_ready+set_done}")
PY
