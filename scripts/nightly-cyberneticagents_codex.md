# CyberneticAgents Nightly Fix Loop (Codex)

You are running on the Hetzner OpenClaw instance.
Repository: `simonvanlaak/CyberneticAgents`
Local path (expected): `/home/simon/.openclaw/workspace/CyberneticAgents` (or equivalent; use the actual path present).

## Goal
Run the nightly usability workflow. If it fails, fix it with **minimal changes** and rerun.
Maximum **3** fix iterations.
Hard max runtime: **2 hours**.

## Commands
- Runner: `bash ./scripts/nightly-cyberneticagents.sh`
- Usability tests: `bash ./scripts/usability.sh`

## Loop
Repeat up to 3 times:
1. Ensure repo is clean and synced:
   - `git fetch origin --prune`
   - `git checkout main`
   - `git reset --hard origin/main`
2. Run: `bash ./scripts/nightly-cyberneticagents.sh`
3. If PASS: stop and report success.
4. If FAIL:
   - Read the latest log under `logs/nightly/`.
   - Identify the smallest fix that makes tests pass.
   - Implement the fix.
   - Add/adjust tests only if necessary.
   - Re-run `bash ./scripts/nightly-cyberneticagents.sh`.

## Git strategy
After a fix that makes tests pass:
- **Bugfix** (tests were failing; fix is small; does not introduce a new capability or intentional behavior change):
  - Commit directly to `main`.
  - Push to `origin main`.

- **Feature / behavior change** (new capability, new default behavior, refactor that changes semantics, or anything that Simon should review):
  - Create branch: `feat/<short-slug>`
  - Commit to the branch.
  - Push branch.
  - Open a PR targeting `main`.

- **Partial fix** (still failing after 3 iterations):
  - Push your best attempt to a branch: `wip/nightly-<date>`
  - Open a PR.
  - Clearly state remaining failures.

## What to include in the morning summary
Provide a short, actionable summary:
- What ran (usability script + tests).
- Result (PASS/FAIL).
- What changed:
  - commit SHAs on main, or
  - PR link(s) + branch names.
- Remaining failures (if any).
- Where to find logs: `logs/nightly/nightly-<timestamp>.log`

## Guardrails
- Never print secrets.
- Prefer minimal diffs.
- Keep commits small and well messaged.
- If missing credentials (GitHub SSH, 1Password token), stop and report exactly what is missing and how to add it.
