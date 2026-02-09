# Architecture Review And Refactor Plan (2026-02-09)

## Scope
Critical review of the current project architecture across runtime, agent orchestration, persistence, RBAC, CLI, and reliability paths.

## Findings (Ordered By Severity)

### 1) Broken legacy entrypoint and inconsistent runtime entry surface
- `main.py` imports non-existent modules (`src.cli.headless`, `src.cli.status`): `main.py:14`, `main.py:40`.
- Verified with `python3 -c "import main"` -> `ModuleNotFoundError: No module named 'src.cli'`.
- Impact: stale/incorrect top-level entrypoint, confusing operational path, and onboarding for new contributors is error-prone.

### 2) Runtime/agent registration relies on private internals of dependencies
- Registration checks private runtime state: `src/registry.py:39` (`runtime._known_agent_names`).
- Agent execution mutates private internals extensively: `src/agents/system_base.py:234`, `src/agents/system_base.py:239`, `src/agents/system_base.py:240`, `src/agents/system_base.py:251`, `src/agents/system_base.py:570`, `src/agents/system_base.py:580`.
- Impact: high fragility to AutoGen upgrades and difficult debugging of side effects.

### 3) RBAC architecture is split into two disconnected enforcers
- General tool permissions use `src/rbac/enforcer.py` backed by `data/rbac.db`: `src/rbac/enforcer.py:33`.
- Skill permissions use separate enforcer/database (`skill_permissions.db`): `src/rbac/skill_permissions_enforcer.py:40`.
- Runtime startup clears general policies each session: `src/cyberagent/cli/headless.py:93`.
- Impact: policy model split-brain, hard-to-reason authorization behavior, and risk of silent policy loss.

### 4) Persistence layer mixes active-record models + service-layer writes with ad-hoc sessions
- Session API is generator-based and consumed via `next(get_db())`: `src/cyberagent/db/db_utils.py:9`.
- Models perform direct writes (`update/add`) and open their own sessions: `src/cyberagent/db/models/task.py:48`, `src/cyberagent/db/models/task.py:53`.
- Pattern appears broadly (64 usages of `next(get_db())` across codebase).
- Impact: transaction boundaries are implicit, multi-step operations are not atomic by default, and consistency bugs become likely.

### 5) Domain/persistence layer leaks orchestration concerns
- DB model returns agent message types directly: `src/cyberagent/db/models/initiative.py:12`, `src/cyberagent/db/models/initiative.py:46`.
- Impact: tighter coupling between persistence and messaging layers, difficult unit isolation, and harder migration to alternate transports.

### 6) Monolithic orchestration modules create change-risk hotspots
- `src/cyberagent/cli/onboarding.py` is 995 LOC.
- `src/agents/system_base.py` is 827 LOC.
- Impact: high merge/conflict rates, slower reviews, and higher regression probability per change.

### 7) Workflow/state transitions are distributed and only partially explicit
- Task lifecycle logic is spread across systems/services (`System1`, `System3`, `tasks` service), without a single state-transition contract.
- Example affected areas: `src/agents/system1.py`, `src/agents/system3.py`, `src/cyberagent/services/tasks.py`.
- Impact: repeated bugs around “completed vs blocked vs review-ready” behavior and weak invariants.

### 8) Queueing/retry is file-based without stronger delivery semantics
- Suggestion and agent queues are local file queues under logs (`src/cyberagent/cli/suggestion_queue.py`, `src/cyberagent/cli/agent_message_queue.py`).
- Retries/dead-letter exist, but no idempotency keys or dedupe protection at consumer boundary.
- Impact: possible duplicate execution and non-deterministic replay behavior after crashes.

## Target Architecture (Desired End State)

1. Single supported entrypoint (`cyberagent`) with `main.py` either removed or reduced to thin compatibility shim.
2. Clear package boundary:
   - `src/cyberagent/*` = source of truth.
   - `src/agents`, `src/rbac`, `src/tools`, `src/registry.py` = compatibility wrappers only during migration.
3. Explicit application service layer for orchestration use-cases with transaction-scoped DB sessions.
4. Unified authorization subsystem (single policy model or explicit bridge with one source of truth).
5. Agent runtime integration via supported APIs/adapters only (no direct mutation of private fields).
6. Explicit workflow state machine for tasks/initiatives with transition guards and policy hooks.
7. Reliable message delivery contract (idempotency + replay-safe processing).

## Refactor Plan (Phased)

## Execution Tracking

### Phase 0 Progress
- [x] Step 1: Fix `main.py` imports to use `src.cyberagent.cli.*`.
- [x] Step 2: Remove/gate runtime startup policy reset (`enforcer.clear_policy()`).
- [x] Step 3: Add CI guardrails for banned imports and private member usage.

### Phase 1 Progress
- [x] Step 1: Replace direct use of `runtime._known_agent_names` with runtime-scoped registration adapter.
- [ ] Step 2: Remove DB model -> agent message coupling.
- [ ] Step 3: Begin transaction-scoped repository migration for task/initiative/procedure run paths.

## Phase 0: Stabilization (1 sprint)
1. Fix entrypoint architecture debt:
   - Replace `main.py` imports with `src.cyberagent.cli.*` or make it a compatibility shim that delegates to `cyberagent`.
2. Stop unsafe policy reset behavior:
   - Remove or gate `enforcer.clear_policy()` from runtime startup.
3. Add architecture guardrails:
   - CI checks for banned imports (`src.cli.*`) and private AutoGen member access (`._known_agent_names`, `._model_client`, `._workbench`, etc.).

Acceptance criteria:
- `python3 -c "import main"` succeeds.
- Runtime restarts do not wipe RBAC policies.
- New private-member usage is blocked in CI.

## Phase 1: Boundary Cleanup (1-2 sprints)
1. Introduce a registration adapter:
   - Replace direct use of `runtime._known_agent_names` with a supported registry abstraction.
2. Extract message mapping from DB models:
   - Move `Initiative.get_assign_message()` behavior into an orchestration/mapping module.
3. Convert active-record writes to repository/service transactions:
   - Begin with `Task`, `Initiative`, and `ProcedureRun` workflows.

Acceptance criteria:
- No DB models import `src.agents.messages`.
- Task lifecycle operations run in explicit transaction scope.

## Phase 2: RBAC Unification (1 sprint)
1. Decide and implement one RBAC source of truth:
   - Either merge tool + skill permissions, or define explicit synchronization contract with shared storage.
2. Add policy bootstrap/versioning:
   - Seed baseline policy deterministically on first run and migrations.

Acceptance criteria:
- One documented policy graph for authorization decisions.
- Integration tests show consistent allow/deny for tool + skill checks.

## Phase 3: Workflow State Machine (1 sprint)
1. Formalize task state model:
   - `pending -> in_progress -> completed|blocked -> approved|rejected` with strict guards.
2. Centralize transitions in task application service:
   - Agents emit intent/events; service enforces transitions.
3. Add review contract:
   - Only review-eligible statuses enter policy review.

Acceptance criteria:
- Transition table documented and enforced by tests.
- No direct status mutation outside task service.

## Phase 4: Runtime Reliability (1 sprint)
1. Add idempotency keys to queued messages.
2. Add processed-message journal for replay-safe startup.
3. Harden dead-letter recovery tooling (`cyberagent inbox`/ops command).

Acceptance criteria:
- Reprocessing the same queue file does not duplicate side effects.
- Crash/restart replay tests pass.

## Phase 5: Decomposition Of Large Modules (ongoing)
1. Split onboarding into focused modules:
   - input validation, technical checks, defaults seeding, discovery orchestration, runtime startup.
2. Split `SystemBase` into:
   - model client adapter, prompt builder, memory context provider, tracing wrapper, message publishing.

Acceptance criteria:
- `onboarding.py` and `system_base.py` each under ~500 LOC.
- Equivalent behavior verified by existing and new regression tests.

## Test Strategy For The Refactor
1. Add architecture tests:
   - banned import paths
   - no private AutoGen field access
   - no DB model -> agent-message imports
2. Expand integration tests around:
   - startup/restart policy persistence
   - task-state transition invariants
   - queue replay/idempotency behavior
3. Keep pre-commit hooks green throughout; land in small atomic commits.

## Risks And Mitigations
1. Risk: broad refactor destabilizes runtime.
   - Mitigation: phase by bounded seams, keep compatibility adapters temporarily.
2. Risk: RBAC behavior changes regress permissions.
   - Mitigation: snapshot existing policies and build approval matrix tests before migration.
3. Risk: workflow changes break UI/status assumptions.
   - Mitigation: add contract tests for `status` and dashboard adapters before transition changes.

## Immediate Next Actions
1. Approve this plan.
2. Create Phase 0 PRD/technical task breakdown with explicit owners.
3. Execute Phase 0 only, then re-review architecture after metrics stabilize.
