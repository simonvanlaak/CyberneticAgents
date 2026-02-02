# Agent Skills PRD

## Document Status
- Status: Draft (implementation-ready)
- Owner: Platform/Architecture
- Last updated: 2026-02-02

## Problem Statement
VSM agents need a standardized, safe, and low-friction way to gain new capabilities over time. Today, tool availability is fragmented and not governed by a clear product contract for packaging, discovery, execution, and permissions.

## Goals
- Provide a flexible skill system that makes adding new agent tool capabilities fast and predictable.
- Standardize tool execution through CLI-based skills executed in Docker.
- Use an explicit industry-facing skill description format (AgentSkills spec) for discovery and invocation metadata.
- Enforce strict permission controls and avoid uncontrolled capability growth in agent context.

## Non-Goals
- No MCP-first tool integration in this phase.
- No write-capable PKM sync in this phase.
- No multi-image packaging strategy in phase 1 (single base image first).

## Product Decisions (Locked)
- Execution model: CLI-only skills for now (not MCP).
- Packaging model: one base Docker image for all tools in phase 1.
- PKM mode: read-only Git sync.
- Permission backend: Casbin remains source of truth.
- Skill limit: maximum 5 skills per system instance.
- Secrets: 1Password is mandatory (no non-1Password credential path in production).

## Users and Stakeholders
- Primary users: System instances (System1/System3/System4/System5) in each team.
- Admin actors: System5 for team-scoped permission CRUD.
- Platform operators: engineering maintaining Docker image, skill registry, and 1Password integration.

## Scope

### In Scope
- Skill metadata registry using AgentSkills-style descriptors.
- Runtime skill loading for agents via CLI executor.
- Tool packaging in a shared Docker image.
- Read-only Git-based PKM skill.
- Casbin-governed permissions at team and system levels.

### Out of Scope
- Automatic inheritance of all team permissions to systems.
- Arbitrary direct host command execution outside the tool container boundary.
- Write/edit operations against PKM repositories.

## Functional Requirements

### FR1: Skill Definition and Discovery
- Each skill must have a machine-readable descriptor (name, description, CLI entrypoint, input schema, output schema, timeout class, required secrets).
- Runtime must expose discoverable skill metadata to agent prompts without injecting full implementation details.
- Initial skills:
  - `web_search` (Brave CLI path)
  - `web_fetch` (readability-based fetch/extract flow)
  - `pkm_readonly_sync` (clone/pull + read from Git repository)

### FR2: Execution Runtime
- Skills execute via Docker-backed CLI executor path used by agents.
- All skills run inside a shared base image in phase 1.
- Execution must support per-skill timeout, stdout/stderr capture, and structured result parsing.
- Image split threshold is defined as 500 MB, but splitting remains a manual product/engineering decision (no automatic size or pull-time measurement required).

### FR3: Credential and Secret Handling
- Skill credentials must be injected via 1Password integration only.
- Skill execution must fail closed when required secrets are unavailable.
- Secrets must not be persisted in repo, logs, or long-lived local files.

### FR4: Skill Limits and Context Control
- Hard limit: each system instance may have at most 5 enabled skills.
- Runtime must refuse skill grants that exceed the per-system limit.
- Agent prompt/tool context must include only enabled skills for that system.

### FR5: Team/System Permission Model
- Team-level permission envelope: defines what skills a team is allowed to grant.
- System-level skill permissions: defines what skills each system instance can execute.
- Systems do not automatically inherit all team-allowed skills.
- System5 in a team can CRUD system skill permissions only within that team envelope.
- Root team has access to all skill permissions and can grant globally.

### FR6: PKM Read-Only Git Sync
- Support cloning/pulling private or public repositories for PKM read workflows.
- Read-only behavior is mandatory in this phase (no commit/push/write-back).
- Access to private repos must use 1Password-managed credentials/tokens.

### FR7: Agent Skills Spec Compliance (Required)
- Skill package layout must follow Agent Skills format:
  - `skill-name/SKILL.md` is required.
  - Optional directories: `scripts/`, `references/`, `assets/`.
- Every `SKILL.md` must contain YAML frontmatter followed by Markdown instructions.
- Required frontmatter fields:
  - `name`
  - `description`
- `name` constraints:
  - 1-64 chars.
  - lowercase letters/numbers/hyphens only.
  - no leading/trailing hyphen, no consecutive hyphens.
  - must match parent directory name.
- `description` constraints:
  - 1-1024 chars.
  - must describe what the skill does and when to use it.
- Optional frontmatter support:
  - `license`, `compatibility`, `metadata`, `allowed-tools` (experimental in the standard).
- Progressive disclosure loading must be implemented:
  1. At startup load only skill metadata (`name`, `description`).
  2. On activation load full `SKILL.md`.
  3. Load `scripts/`, `references/`, `assets/` on demand only.
- Keep `SKILL.md` concise for progressive disclosure efficiency:
  - Target <5000 tokens for instructions.
  - Target under 500 lines, moving deeper detail into referenced files.
- Runtime should support skill validation in CI with the reference validator (`skills-ref validate`).
- Prompt injection of available skills must include concise metadata for matching.
- For filesystem-style execution include skill `location` in prompt metadata; for tool-based execution `location` may be omitted.

## Permission and Architecture Alignment
- System instance service reference: `src/cyberagent/services/systems.py`.
- Team instance service reference: `src/cyberagent/services/teams.py`.
- Team policy actor reference: `src/agents/system5.py`.
- Detailed permission requirements are specified in `docs/planned_features/skill_permissions_prd.md`.

## Non-Functional Requirements
- Reliability: failed skills return deterministic error envelopes.
- Security: strict least-privilege for secrets and repository access.
- Performance: tool invocation overhead acceptable for interactive CLI loops.
- Operability: logs include skill id, duration, exit status, and permission decision trace id.
- Context efficiency: skill loading follows progressive disclosure and keeps base metadata concise.

## Acceptance Criteria
- Agent can list and execute only skills explicitly granted to its system instance.
- Team cannot grant skills outside its team envelope.
- System5 can grant/revoke skills within allowed team scope.
- Root team can grant any supported skill.
- Attempts to assign a 6th skill to a system are rejected with clear error.
- Skills requiring secrets fail with actionable errors when 1Password values are missing.
- PKM skill can read from private Git repo without allowing writes.
- Skill folders pass Agent Skills structural and frontmatter validation.
- Startup prompt includes only skill metadata; full instructions/resources are loaded only when activated.

## Rollout Plan
- Phase A: skill descriptor schema + registry + read path in prompts.
- Phase B: base Docker image with initial skills and executor integration.
- Phase C: Casbin-backed team/system permission flows + System5 CRUD tools.
- Phase D: PKM read-only sync skill + private repo credential handling.
- Phase E: hard-limit enforcement + observability and audit hooks.

## Risks and Mitigations
- Large base image slows developer loop.
  - Mitigation: keep base image lean; manually split by tool groups when approaching/exceeding 500 MB.
- Permission sprawl or privilege escalation.
  - Mitigation: team envelope + system grants + Casbin enforcement + audit logging.
- Secret leakage through tool output.
  - Mitigation: sanitize logs, fail closed on missing secret wiring, enforce 1Password-only path.

## Open References
- AgentSkills: `https://agentskills.io/home`
- AgentSkills Specification: `https://agentskills.io/specification`
- AgentSkills Integration Guide: `https://agentskills.io/integrate-skills`
- ClawHub: `https://www.clawhub.com/`
