# CyberneticAgents — OpenClaw Test Instructions

This file is the **repeatable test plan** for verifying CyberneticAgents works end-to-end on the Hetzner OpenClaw instance.

## Goal of the test
1) Ensure **onboarding + runtime** are working (background runtime actually runs).
2) Ensure the system can **collect/consume user identity context** without getting stuck on “insufficient info” errors (Issue #40 regression check).
3) Ensure we can **drive the system via CLI** (preferred) and optionally verify Telegram routing.

## Test user / onboarding interview answer (canonical)
When the onboarding interview asks:
> “What is the most important outcome you want CyberneticAgents to help you achieve?”

Answer with:
> **I want agents to help me finish my bachelor thesis in product management at Code University.**

## Preconditions
- Workdir: `/root/.openclaw/workspace/CyberneticAgents`
- Venv exists: `.venv/`
- Docker running (for CLI tools executor image).

Activate:

```bash
cd /root/.openclaw/workspace/CyberneticAgents
source .venv/bin/activate
```

## 1) Clean-ish start (runtime sanity)
```bash
cyberagent restart
cyberagent status
```

Expected:
- Team exists (e.g. `Team 1: root`)
- Strategy shows (often `Onboarding SOP`)
- Runtime reports it’s running in background (pid printed on start/restart)

## 2) Complete onboarding (if needed)
Run onboarding:
```bash
cyberagent onboarding
```

Notes / common pitfall:
- The interactive PKM selector has previously glitched and injected literal strings like `ArrowDown` into the “repo URL” prompt.
- If PKM sync fails, choose to **continue without PKM** (the test can proceed).

## 3) Answer onboarding interview via CLI inbox (preferred)
Check inbox:
```bash
cyberagent inbox --answered
```

If there is a pending system question (Q1), resolve it by providing the canonical answer.

### Option A (manual, if you’re running a stdin-driven CLI session)
If you are in a flow that prompts `User:` in the terminal, simply paste the answer.

### Option B (headless, deterministic; preferred for OpenClaw)
Send the answer straight into the **UserAgent** (this reliably creates a `user_prompt` in the CLI channel and unblocks the interview flow):

```bash
cyberagent dev system-run "UserAgent/root" \
  "I want agents to help me finish my bachelor thesis in product management at Code University."
```

Re-check:
```bash
cyberagent inbox --answered
```

Expected:
- The oldest pending Q1 becomes `answered`.

## 4) Trigger work (so tasks actually run)
On some builds, onboarding ends with **no initiatives** and expects you to create one via `suggest`.

Create a small test initiative:
```bash
cyberagent suggest "Create an initiative for helping me finish my bachelor thesis. Start by collecting the minimal identity context you need, then propose the next 3 steps."
```

Then watch:
```bash
cyberagent watch --channel cli --session-id cli-main --interval 2
```

Stop watch with Ctrl+C.

## 5) Verify Issue #40 behavior (identity context injection)
What we’re looking for:
- Previously, a System1 identity-related task could fail due to missing user context.
- With the fix, the agent should proceed using injected `user_profile` context rather than repeatedly blocking.

Procedure:
1) After the suggest in step (4), run:
   ```bash
   cyberagent status
   ```
2) If tasks are created, look for anything like “collect identity”, “user profile”, “disambiguation links”, etc.
3) If it’s still unclear, inspect logs:
   ```bash
   cyberagent logs --tail 200
   ```

Pass criteria:
- No repeated “insufficient identity info” / “missing identity” block loops.
- The system either:
  - proceeds with reasonable assumptions, or
  - asks a **single** clear question via inbox and continues once answered.

## 6) Optional: Telegram smoke test
Telegram is useful but **not required** for the core test.

- OpenClaw bot group (cyberagents-test): chat id `-5252723593` (mentions required).
- CyberneticAgents bot: `@cybernetic_agents_svl_bot` (DM is the reliable onboarding path).

## 7) Record results
When you run this test, record:
- Date/time
- Whether onboarding needed rerun
- Whether inbox Q1 was answered successfully
- Whether tasks started showing up in `cyberagent status`
- Any errors + the relevant `cyberagent logs --tail ...` snippet

---

If this plan drifts from reality (CLI flags changed, paths changed, etc.), update this file immediately so the next run is deterministic.
