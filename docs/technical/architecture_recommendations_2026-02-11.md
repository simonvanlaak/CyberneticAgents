# Architecture Change Recommendations (2026-02-11)

Project item reference: GitHub issue `#58` (Project 1, status lifecycle managed in GitHub Project).

## Scope
This recommendation is based on direct review of the current codebase (not historical assumptions), with emphasis on runtime composition, CLI/onboarding flow, persistence boundaries, RBAC boundaries, and operability.

## Current Architecture Snapshot (Verified)
1. Transitional layout is still active: `src/cyberagent/*` coexists with `src/agents`, `src/rbac`, `src/tools`, and `src/registry.py`.
2. The packaged CLI entrypoint is `cyberagent` via `src.cyberagent.cli.cyberagent:main` (`pyproject.toml:35-36`), while `main.py` remains a second entry surface.
3. Two orchestration hotspots exceed 1000 LOC:
   - `src/cyberagent/cli/onboarding.py` (1059 lines)
   - `src/cyberagent/cli/onboarding_discovery.py` (1039 lines)
4. The pre-commit hook blocks staged Python files over 1000 lines (`git-hooks/pre-commit:11-13`). This makes those hotspots expensive to change safely.
5. Onboarding runs technical checks before collecting/validating onboarding inputs (`src/cyberagent/cli/onboarding.py:144`, `src/cyberagent/cli/onboarding.py:147`).
6. Technical secret checks are global across all skill metadata (`src/cyberagent/cli/onboarding.py:916-920`), which has already caused sequencing bugs when secrets should be conditional on later onboarding choices.
7. `onboarding_discovery` calls back into a private onboarding function through a local import (`src/cyberagent/cli/onboarding_discovery.py:103`, `src/cyberagent/cli/onboarding_discovery.py:116`), which indicates boundary/cycle pressure.
8. New-namespace runtime code still depends on legacy agent namespace:
   - `src/cyberagent/cli/headless.py:11-12,34`
   - `src/cyberagent/cli/cyberagent.py:31,77`
   - `src/cyberagent/channels/telegram/poller.py:12`
   - `src/cyberagent/channels/telegram/webhook.py:15`
9. Persistence style remains mixed: active-record style model methods (`src/cyberagent/db/models/task.py:48-59`) and service-layer persistence (`src/cyberagent/services/tasks.py`) coexist; `next(get_db())` occurs broadly (67 usages in `src/`).
10. Authorization has two enforcers and models (`src/rbac/enforcer.py`, `src/rbac/skill_permissions_enforcer.py`) with optional shared DB URL (`src/rbac/authz_db.py`), but still separate policy/model surfaces.

## Recommended Changes (Prioritized)

### P0: Split onboarding orchestration by phase and responsibility
Recommendation:
1. Break `onboarding.py` into narrow modules:
   - `onboarding_orchestrator.py` (flow)
   - `onboarding_technical_checks.py` (environment/infra checks)
   - `onboarding_bootstrap.py` (team/system/procedure seeding)
   - `onboarding_runtime.py` (runtime/dashboard startup)
2. Break `onboarding_discovery.py` into:
   - PKM adapters (GitHub/Notion)
   - profile discovery
   - summary rendering/storage
3. Replace private callback import (`onboarding_discovery -> onboarding._apply_onboarding_output`) with a shared service function in a neutral module.

Why now:
- This is the highest architecture risk and currently constrained by the 1000-line pre-commit rule.
- It directly impacts onboarding reliability and change velocity.

Acceptance criteria:
1. No onboarding module over 700 LOC.
2. No local cross-import to private onboarding functions.
3. Existing onboarding tests continue passing.

### P1: Make technical checks context-aware (phase-gated secrets)
Recommendation:
1. Separate "always-required at startup" secrets from "conditional by selected PKM/tooling" secrets.
2. Evaluate conditional secrets only after `_validate_onboarding_inputs` determines selected PKM mode.
3. Keep skill metadata (`required_env`) for runtime/tool execution, but do not treat all required env vars as unconditional onboarding gates.

Why now:
- Current global secret sweep in `run_technical_onboarding_checks` is a structural source of sequencing regressions.

Acceptance criteria:
1. Technical checks do not fail for PKM-specific secrets before PKM choice is known.
2. Add regression tests for conditional-secret gating behavior.

### P2: Formalize the compatibility boundary for legacy namespaces
Recommendation:
1. Create `src/cyberagent/agents/` as the canonical namespace.
2. Keep `src/agents/*` as compatibility wrappers only (thin re-export/deprecation path).
3. Move runtime-facing imports in CLI/channels from `src.agents.*` and `src.registry` to canonical `src/cyberagent/*` modules.

Why now:
- The current dependency direction keeps migration incomplete and increases cognitive overhead.

Acceptance criteria:
1. No imports from `src.agents` or `src.registry` in `src/cyberagent/cli/*` and `src/cyberagent/channels/*`.
2. Compatibility wrappers preserved until migration completion.

### P3: Finish persistence boundary consolidation (unit-of-work over mixed writes)
Recommendation:
1. Introduce a standard session context (unit-of-work helper) for service-level operations.
2. Deprecate active-record write methods (`add`, `update`) in DB model classes.
3. Restrict DB model modules to schema/queries; keep mutations in service/repository layer.

Why now:
- Mixed write patterns complicate transaction boundaries and reviewability.

Acceptance criteria:
1. No model write methods used by application flows.
2. `next(get_db())` usage significantly reduced in CLI and model modules.

### P4: Introduce a single authorization facade
Recommendation:
1. Add `src/cyberagent/authz/` facade APIs for permission checks and grants.
2. Keep two Casbin models if needed, but hide them behind one domain API.
3. Centralize policy bootstrap/version checks through the facade.

Why now:
- Reduces duplicated authorization logic and simplifies auditability.

Acceptance criteria:
1. Callers use facade APIs only.
2. Enforcer-specific details are isolated to authz internals.

### P5: Add an internal queue abstraction with swappable backend
Recommendation:
1. Define queue interface used by headless runtime.
2. Keep current file-backed implementation as default.
3. Add SQLite-backed implementation for stronger multi-process safety and ops introspection.

Why now:
- Current file queues are workable but operationally fragile under concurrency and external file manipulation.

Acceptance criteria:
1. Runtime queue operations use interface, not direct file logic.
2. File backend and SQLite backend pass the same contract tests.

### P6: Expand architecture guardrails
Recommendation:
1. Extend architecture tests to block:
   - `src/cyberagent/*` importing legacy namespaces directly (except approved compatibility modules).
   - circular/private callback import patterns in onboarding modules.
2. Add a guardrail test for max Python file size in key orchestration namespaces (align with hook limits).

Why now:
- Prevents architectural regressions after refactor slices land.

Acceptance criteria:
1. New guardrail tests run in CI.
2. Violations fail fast before runtime regressions occur.

## Sequenced Execution Plan
1. Sprint 1: P0 module split skeleton + P1 conditional-secret gating + regression tests.
2. Sprint 2: P0 completion and callback decoupling; begin P2 import migrations.
3. Sprint 3: P2 completion + start P3 unit-of-work introduction in onboarding/services paths.
4. Sprint 4: P3 continuation + P4 authz facade + P6 guardrails.
5. Sprint 5: P5 queue interface + SQLite backend + contract tests.

## Success Metrics
1. `src/cyberagent/cli/onboarding.py` and `src/cyberagent/cli/onboarding_discovery.py` each < 700 LOC.
2. Zero direct `src.agents` imports from `src/cyberagent/cli/*` and `src/cyberagent/channels/*`.
3. No onboarding regressions related to pre-PKM secret gating.
4. Reduced `next(get_db())` direct usage in CLI/model layers.
5. Guardrail tests protect the new boundaries.

## Notes
This plan is intentionally incremental and compatible with the current migration convention (legacy paths remain stable until migration completion).
