# Onboarding Background Research Not Starting (2026-02-09)

## Summary
- After onboarding restart and first Telegram response, expected background research (repo/profile-link analysis) does not start.
- Runtime remains in interview Q&A mode only.
- Onboarding initiative tasks are not started/assigned, so no research tasks execute.

## Current State Observed
- `cyberagent status` shows:
  - `Initiative 1 [PENDING]: First Run Discovery`
  - Tasks 1-6 are `PENDING` with assignee `-` (unassigned).
- This confirms task execution pipeline did not start.

## Evidence From Runtime Logs
- File: `logs/runtime_20260209_005323.log`
- System4 receives onboarding/interview prompt and user answer, then calls `ContactUserTool` again to ask a next question.
- Prompt snapshot in log shows:
  - `# SKILLS` -> `No skills available`
  - Toolset contains only policy/strategy/procedure/user-contact tools.
  - No web research or repo analysis tool invocation.
- UserAgent logs show pending-question mismatch symptoms:
  - `Pending question (System4): What is the most important outcome ...`
  - Followed by `Message could not be serialized` / response `NoneType`.

## Root Cause Analysis
1. Onboarding execution path is not advancing to active task assignment.
   - Since initiative/tasks remain pending and unassigned, System3 has not assigned any System1 task yet.
2. Telegram interview flow in System4 is not wired to execute discovery pipeline research actions after each answer.
   - It asks follow-up questions via `ContactUserTool` only.
3. Runtime context shows no research skills/tools available to System4.
   - Even with interview instruction text asking for background research, there is no concrete tool call path for link/repo crawling in that loop.
4. Pending question resolution path appears inconsistent, causing stale pending question state.

## Relevant Code Paths
- Interview dispatch:
  - `src/cyberagent/cli/onboarding_interview.py`
  - `src/agents/system4.py` (`handle_user_message`)
- Onboarding background discovery starter:
  - `src/cyberagent/cli/onboarding.py` (`_start_discovery_background`)
  - `src/cyberagent/cli/onboarding_discovery.py`
- Task assignment pipeline:
  - `src/agents/system3.py` (`handle_initiative_assign_message`)
- Pending question routing/state:
  - `src/agents/user_agent.py`
  - `src/cyberagent/channels/inbox.py`
  - `src/tools/contact_user.py`

## Expected Behavior
- After onboarding starts and first user answer arrives:
  - Discovery/background research should run for provided repo/profile links.
  - Initiative 1 should move into execution with at least one task assigned/in progress.
  - Pending question state should resolve correctly per channel/session.

## Impact
- Onboarding appears active to the user, but autonomous discovery/research does not begin.
- User must continue manual Q&A without expected background enrichment.
- Initial strategy context quality is degraded due to missing repo/profile evidence.

## Next-Session Handoff Notes
- Snapshot timestamp:
  - Runtime log analyzed: `logs/runtime_20260209_005323.log`
  - UTC check during analysis: `2026-02-08 23:47:32 UTC`
- Database state at time of report:
  - `procedure_runs`: `(id=1, procedure_id=1, initiative_id=1, status='started')`
  - `initiatives`: initiative `1` = `First Run Discovery`, status `PENDING`
  - `tasks` for initiative `1`: all `PENDING`, all `assignee=NULL`
- Queue state:
  - `logs/agent_message_queue`: `0` files (no queued initiative/task message waiting)
- Relevant symptom chain:
  - System4 asks next question with `ContactUserTool(wait_for_response=true)`.
  - UserAgent logs pending question still present, then respond path logs `Message could not be serialized` and resolves `NoneType`.
  - No observed `initiative_assign` delivery for this onboarding cycle.

## Fast Re-Check Commands
```bash
cyberagent status
cyberagent logs --level ERROR --limit 120
cyberagent logs --level WARNING --limit 120
ls -1t logs/runtime_*.log | head -n 1
rg -n "Pending question|Message could not be serialized|ContactUserTool|initiative_assign|No skills available" logs/runtime_*.log -S
python3 - <<'PY'
import sqlite3
con=sqlite3.connect('data/CyberneticAgents.db')
cur=con.cursor()
print('procedure_runs:', list(cur.execute("select id,procedure_id,initiative_id,status from procedure_runs order by id desc limit 5")))
print('initiative 1:', list(cur.execute("select id,name,status from initiatives where id=1")))
print('tasks i1:', list(cur.execute("select id,name,status,assignee from tasks where initiative_id=1 order by id")))
PY
```
