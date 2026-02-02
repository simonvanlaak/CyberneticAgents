# Architecture Refactor Plan (Step-by-Step)

This plan operationalizes the target architecture from `docs/technical/architecture_perfect_plan.md` while minimizing risk and avoiding feature regressions.

## Goals
- Preserve current behavior while moving files.
- Avoid breaking CLI and agent workflows.
- Reduce coupling between domain logic and infrastructure.
- End with clean module boundaries and stable public APIs.

## Guardrails (Non‑Negotiable)
- No functional changes during structural moves.
- Keep CLI behavior and agent interactions unchanged at each step.
- Use re-export shims until all imports are updated.
- Run tests after each phase (or after each small batch).

## Success Criteria
- All tests pass at the end of each phase.
- No changes to CLI surface or agent behavior.
- Clean dependency direction: `domain -> services -> agents/tools`.

## Migration Checklist
- [x] Phase 0 — Baseline & Safety
- [x] Phase 1 — Create `src/cyberagent/` Package Root
- [x] Phase 2 — Core + DB Infrastructure Moves
- [x] Phase 3 — Domain vs DB Split
- [x] Phase 4 — Services Layer
- [x] Phase 5 — Tools Simplification
- [x] Phase 6 — Agents Cleanup
- [x] Phase 7 — CLI & UI
- [x] Phase 8 — Remove Legacy Paths
- [x] Phase 9 — Document New Architecture
- [ ] Phase 10 - Run all tests & git push

## Phase 0 — Baseline & Safety
**Purpose:** lock current behavior and reduce risk.

Actions:
1. Run full test suite and capture baseline:
   ```bash
   python3 -m pytest tests/ -v
   ```
2. Add a migration checklist doc (optional): list the core workflows to validate after each phase.
3. Ensure `src/` imports are consistent (avoid ad-hoc relative imports).

Exit Criteria:
- Baseline tests pass.
- Known workflows are documented for regression testing.

---

## Phase 1 — Create `src/cyberagent/` Package Root
**Purpose:** introduce the new namespace without moving logic yet.

Actions:
1. Create `src/cyberagent/__init__.py`.
2. Add re-export shims to keep old imports working.
3. No file moves yet.

Exit Criteria:
- All tests pass.
- Existing imports still work.

---

## Phase 2 — Core + DB Infrastructure Moves
**Purpose:** move low-risk infrastructure first.

Targets:
- `src/runtime.py` -> `src/cyberagent/core/runtime.py`
- `src/logging_utils.py` -> `src/cyberagent/core/logging.py`
- `src/team_state.py` -> `src/cyberagent/core/state.py`
- `src/db_utils.py` + `src/init_db.py` -> `src/cyberagent/db/`

Actions:
1. Move one file at a time, add shim at old path.
2. Update imports in `core/` only after shim is in place.

Exit Criteria:
- Tests pass.
- CLI runtime still starts.

---

## Phase 3 — Domain vs DB Split
**Purpose:** isolate pure domain logic from persistence.

Actions:
1. Move SQLAlchemy models to `src/cyberagent/db/models/`.
2. Extract non-DB logic into `src/cyberagent/domain/`.
3. Keep a thin DB layer with session + Base.

Exit Criteria:
- Domain logic is database‑free.
- Model imports are updated and tests pass.

---

## Phase 4 — Services Layer
**Purpose:** centralize orchestration logic outside agents/tools.

Actions:
1. Create `src/cyberagent/services/`.
2. Move coordination logic (strategy/task/policy flows) into services.
3. Update agents/tools to call services.

Exit Criteria:
- Agents/tools are thin.
- Service tests cover core workflows.

---

## Phase 5 — Tools Simplification
**Purpose:** tools become adapters only.

Actions:
1. Move tools under `src/cyberagent/tools/`.
2. Tools call services and do minimal IO.
3. Remove any DB/model imports from tools.

Exit Criteria:
- Tools only depend on services + rbac.

---

## Phase 6 — Agents Cleanup
**Purpose:** keep agents focused on messaging, not orchestration.

Actions:
1. Remove direct DB/model access from agents where possible.
2. Route through services for side‑effects.
3. Confirm tool injection still works.

Exit Criteria:
- Agents depend on `services`, `domain`, `tools`, `rbac` only.

---

## Phase 7 — CLI & UI
**Purpose:** ensure CLI depends only on services/core.

Actions:
1. Move CLI modules to `src/cyberagent/cli/`.
2. Remove direct agent dependencies from CLI.
3. If UI is unused, remove UI code and tests.

Exit Criteria:
- CLI uses services + core only.

---

## Phase 8 — Remove Legacy Paths
**Purpose:** delete old `src/*` entry points and shims.

Actions:
1. Remove all legacy re-export shims.
2. Delete old modules that were moved.
3. Update docs to only reference new namespace.

Exit Criteria:
- Clean tree and passing tests.
- [x] README references the new layout and entry points.
- [ ] AGENTS instructions mention the refactor and any new conventions (TBD).

---

## Phase 9 — Document New Architecture
**Purpose:** make the refactor visible to contributors by updating the main docs and guidance files.

Actions:
1. Update `README.md` to describe the new `src/cyberagent/` package, mention where CLI, agents, tools, and DB code now live, and refresh any setup or run instructions that referenced the old paths.
2. Revise `AGENTS.md` (and any linked guide) to call out the new architecture, the enforced TDD workflow, and the location of critical modules (core, services, tools).
3. Refresh any other docs (e.g., `docs/technical/`, `docs/planned_features/`) that still point at legacy modules, and add quick start commands reflecting the refactor.
4. Add a short checklist in this doc to capture the doc updates and call out any follow-ups.

Phase 9 checklist (current snapshot):
- [x] Update `README.md` project structure to reflect the current hybrid layout (`src/cyberagent/*` plus remaining legacy modules under `src/`).
- [x] Update `AGENTS.md` key components and import examples to use current module locations (for example `src/cyberagent/core/runtime.py` instead of `src/runtime.py`).
- [x] Sweep `docs/planned_features/` and `docs/technical/` for stale path references and either update or mark them as historical.
- [x] Add a "known transitional modules" note in docs for still-active legacy paths (`src/agents/`, `src/tools/`, `src/rbac/`, `src/registry.py`).
- [x] Re-run path checks after doc edits:
  ```bash
  rg -n "src/(runtime\\.py|logging_utils\\.py|team_state\\.py|db_utils\\.py|init_db\\.py|models/|cli/)" README.md AGENTS.md docs -g '*.md'
  ```

Exit Criteria:
- Contributors can find the current architecture and entry points from README/AGENTS.
- No mention of deleted paths remains in the primary docs.
- A follow-up task list exists for future doc cleanups (if needed).

---

## Phase 10 — Run Full Verification and Push
**Purpose:** confirm the refactor is stable, then publish.

Actions:
1. Run the full suite locally:
   ```bash
   python3 -m pytest tests/ -v
   ```
2. Run repo quality checks (when tools are installed):
   ```bash
   python3 -m black --check src/ tests/
   python3 -m mypy src/ --ignore-missing-imports
   ```
3. Ensure git hooks pass (`pre-commit`, `pre-push`) without `--no-verify`.
4. Commit only scoped refactor/doc updates.
5. Push branch after tests + hooks succeed.

Exit Criteria:
- Full tests pass on the final branch tip.
- Required hooks pass.
- Remote branch is updated with scoped commits.

---

## Current Status Snapshot (2026-02-02)
- `src/cyberagent/core/`, `src/cyberagent/db/`, `src/cyberagent/domain/`, `src/cyberagent/services/`, and `src/cyberagent/cli/` are present.
- Legacy modules are still present in `src/` (not yet fully consolidated), so documentation must describe a transitional architecture accurately.
- Phase 9 documentation updates are complete; Phase 10 remains open for final full verification and push.

## Regression Checks (Run Frequently)
- `python3 -m pytest tests/agents/ -v`
- `python3 -m pytest tests/cli/ -v`
- `python3 -m pytest tests/tools/ -v`
- Manual check: OpenClaw tool execution from a System agent.

---

## Notes
- Use one move per commit where possible.
- Keep shims until the end to avoid breaking imports mid‑refactor.
- Keep `AGENTS.md` instructions in mind (TDD, hooks).
