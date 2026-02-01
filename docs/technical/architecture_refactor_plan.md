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
- [ ] Phase 8 — Remove Legacy Paths

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

---

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
