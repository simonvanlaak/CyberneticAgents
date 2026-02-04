# Security Audit Plan (Full Project)

## Objectives
1. Identify vulnerabilities in code, dependencies, and runtime configuration.
2. Verify data protection, privacy, and auditability requirements.
3. Validate RBAC/VSM enforcement and skill permission boundaries.
4. Ensure supply-chain and deployment hardening.

## Scope
1. Application code in `src/` and `main.py`.
2. Config and secrets handling (`.env.example`, `pyproject.toml`, runtime env).
3. Data stores (`data/`, `security_logs.db`, `data/rbac.db`).
4. CLI tooling and skill execution paths.
5. Docs for security-critical behavior (memory, RBAC, observability).

## Phase 0: Prep
1. Define threat model and assets (PII, tokens, memory artifacts, audit logs).
2. Enumerate entry points (CLI, tools, agent skill APIs).
3. Establish audit evidence checklist and report template.

## Phase 1: Static Review
1. Manual code review for authz/authn boundaries (RBAC, VSM).
2. Input validation review for all CLI and skill entry points.
3. Data handling review for memory and audit logs (redaction, retention).
4. Secrets and config review (no plaintext, no hardcoded tokens).
5. File system access review for tools and CLI executor.

## Phase 2: Dependency & Supply Chain
1. Review `pyproject.toml` dependencies for known CVEs.
2. Validate lockfile usage (if any) and pinning strategy.
3. Confirm build and runtime images for CLI tooling are minimal.
4. Verify license compliance for key deps.

## Phase 3: Dynamic & Behavioral Tests
1. Permission bypass tests for `memory_crud` and RBAC paths.
2. Namespace and scope isolation tests (agent/team/global).
3. Adversarial prompt and tool injection tests for CLI executor.
4. Audit log integrity tests (no sensitive payloads logged).

## Phase 4: Data & Storage Security
1. Check storage paths and permissions for `data/` and logs.
2. Validate delete/redaction behavior for memory.
3. Verify backup/retention posture for DBs and logs.

## Phase 5: Deployment & Ops
1. Review docker-compose and runtime env configuration.
2. Validate least-privilege for runtime execution.
3. Confirm monitoring and alerting for security events.

## Deliverables
1. Findings report with severity, impact, and remediation.
2. Patch plan with owners and timelines.
3. Verification tests for fixed issues.

## Exit Criteria
1. High/critical findings remediated or accepted with documented risk.
2. Security tests added where applicable and passing.
3. Docs updated for security-relevant behavior changes.
