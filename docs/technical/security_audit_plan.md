# Security Audit Plan (Full Project)

## Objectives
1. Identify vulnerabilities in code, dependencies, and runtime configuration.
2. Verify data protection, privacy, and auditability requirements.
3. Validate RBAC/VSM enforcement and skill permission boundaries.
4. Ensure supply-chain and deployment hardening.
5. Produce repeatable evidence for recurring audits.

## Scope
1. Application code in `src/` and `main.py`.
2. Config and secrets handling (`.env.example`, `pyproject.toml`, runtime env).
3. Data stores (`data/`, `data/security_logs.db`, `data/rbac.db`).
4. CLI tooling and skill execution paths.
5. Docs for security-critical behavior (memory, RBAC, observability).
6. Scheduled recurring audit cadence and evidence retention.

## Audit Cadence (Recurring)
1. Frequency: monthly.
2. Triggered audits: before any major release or security-sensitive refactor.
3. Evidence retention: temporary artifacts may be created during the audit but must be deleted after completion and never committed. Only a redacted summary may be retained in the audit report.

## Phase 0: Prep
1. Define threat model and assets (PII, tokens, memory artifacts, audit logs).
2. Enumerate entry points (CLI, tools, agent skill APIs).
3. Establish audit evidence checklist and report template.
4. Confirm audit is manual-only; no automated security scanning requirements beyond explicit steps below.

### Threat Model (Project-Specific)
1. Assets:
2. `data/rbac.db` (authorization policy).
3. `data/security_logs.db` (security events and audit signals).
4. `data/` memory stores (agent/team/global).
5. Environment secrets (API keys, service tokens, OnePassword session data).
6. Attackers:
7. Untrusted CLI users.
8. Malicious tool/skill payloads.
9. Misconfigured or compromised agents.
10. Supply-chain threats in dependencies and tool images.
11. Trust Boundaries:
12. CLI input to runtime.
13. Skill execution boundary (CLI executor).
14. RBAC enforcement and namespace resolution.
15. Data persistence boundary (`data/` and logs).

## Phase 1: Static Review
1. Manual code review for authz/authn boundaries (RBAC, VSM).
2. Input validation review for all CLI and skill entry points.
3. Data handling review for memory and audit logs (redaction, retention).
4. Secrets and config review (no plaintext, no hardcoded tokens).
5. File system access review for tools and CLI executor.
6. Identify all security-sensitive modules and invariants.

### Security-Sensitive Modules (Must Review Each Audit)
1. RBAC and namespace parsing: `src/rbac/`.
2. Skill permission enforcement: `src/rbac/skill_permissions_enforcer.py`.
3. CLI executor and skill runtime: `src/cyberagent/tools/cli_executor/`.
4. Memory CRUD, permissions, and scopes: `src/cyberagent/memory/`.
5. Observability/audit logging: `src/cyberagent/memory/observability.py`.
6. Secrets handling: `src/cyberagent/secrets.py` and `.env.example`.
7. Data persistence initialization: `src/cyberagent/db/` and `src/rbac/enforcer.py`.

### Static Invariants (Must Hold)
1. Skill invocations enforce RBAC before executing any CLI tool command.
2. Memory CRUD enforces scope defaults and permission checks before any store access.
3. Namespace is required for team/global scope; agent scope defaults to actor ID.
4. No secrets are logged in audit or observability logs.
5. All persistent data stores reside under `data/` (requirement).

## Phase 2: Dependency & Supply Chain
1. Review `pyproject.toml` dependencies for known CVEs.
2. Validate lockfile usage (if any) and pinning strategy.
3. Confirm build and runtime images for CLI tooling are minimal.
4. Verify license compliance for key deps.
5. Identify transitive dependency risks.

### Dependency Audit Rules
1. CVE threshold: no unpatched critical or high CVEs.
2. If no lockfile, capture dependency versions via `python3 -m pip freeze`.
3. Verify docker images are pinned by digest when used in production.
4. Record license summary for new or updated dependencies.

## Phase 3: Dynamic & Behavioral Tests
1. Permission bypass tests for `memory_crud` and RBAC paths.
2. Namespace and scope isolation tests (agent/team/global).
3. Adversarial prompt and tool injection tests for CLI executor.
4. Audit log integrity tests (no sensitive payloads logged).
5. Verify deny-by-default for unknown tools.

### RBAC/VSM Test Matrix (Must Execute)
1. Team scope read: Sys1/Sys2 allowed, Sys3+ allowed.
2. Team scope write: Sys3+ allowed, Sys1/Sys2 denied.
3. Global scope read/write: Sys4 only.
4. Agent scope: owner only; cross-team access denied.
5. Namespace mismatch: denied.

## Phase 4: Data & Storage Security
1. Check storage paths and permissions for `data/` and logs.
2. Validate delete/redaction behavior for memory.
3. Verify backup/retention posture for DBs and logs.
4. Confirm `security_logs.db` is stored under `data/`.
5. Confirm no persistent DBs or logs exist outside `data/`.
6. Allowed exceptions (must be ephemeral and removed after audit):
7. `/tmp` or OS temp directories for transient files.
8. `.pytest_cache` and local test caches during execution.
9. Docker volumes or containers used by CLI tools (must be pruned/removed after audit).
10. Tool execution work dirs created during the audit (must be deleted after completion).

## Phase 5: Deployment & Ops
1. Review docker-compose and runtime env configuration.
2. Validate least-privilege for runtime execution.
3. Confirm monitoring and alerting for security events.
4. Confirm secrets are injected only at runtime and not persisted.
5. Document the CLI tools image provenance (source repo, tag, and digest when used in production).

## Deliverables
1. Findings report with severity, impact, and remediation.
2. Patch plan with owners and timelines.
3. Verification tests for fixed issues.
4. Evidence summary only (no stored logs, command outputs, or artifacts).
5. Audit summary markdown file saved under `docs/technical/security/` named with the current date (YYYY-MM-DD) that includes:
6. A concise audit summary (scope, dates, tools run).
7. A clear, enumerated list of vulnerabilities with severity, impact, and status.

## Exit Criteria
1. High/critical findings remediated or accepted with documented risk.
2. Security tests added where applicable and passing.
3. Docs updated for security-relevant behavior changes.

## Evidence Checklist (Minimum)
1. `git rev-parse HEAD` captured for the audit baseline.
2. `python3 -m pytest tests/ -v` executed and outcome recorded in the report.
3. `python3 -m pip freeze` executed and summarized in the report.
4. Summary of RBAC/VSM matrix test results.
5. Dependency CVE review notes with remediation decisions.
6. Confirmation that `data/` contains all persisted DBs and logs.
7. Confirmation that ephemeral audit artifacts were deleted post-audit (list of removed paths).

## Gap Closures (Required Actions)
1. Deny-by-default tool execution:
2. Manual step: attempt to invoke an unknown skill/tool via CLI executor; verify explicit deny/error.
3. Log output must show a permission denial or "unknown tool" error without executing a command.
4. Secrets redaction verification:
5. Manual step: force a controlled failure containing a dummy secret token and verify logs do not include it.
6. Document redaction behavior and add a checklist item in the audit report.
