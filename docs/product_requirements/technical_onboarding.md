# Planned Feature – Technical Onboarding (Prerequisites & Permissions)

Before onboarding begins, run a technical checklist to ensure the CLI can operate safely and the runtime can start.

## Required Checks
1. Database writable: `data/` exists and the SQLite file can be created/updated.
2. Logs writable: `logs/` exists and is writable for runtime logs.
3. Docker availability: all tool/skill executions run in Docker; Docker must be installed, reachable, and the daemon running.
4. 1Password CLI authentication when tool secrets are required:
   - `op` auth must be available via `OP_SERVICE_ACCOUNT_TOKEN` or an `OP_SESSION_*`.
   - Secrets must exist in the vault with names matching required env vars.
   - Prompt the user to add all API keys used by this project to the 1Password vault
     before onboarding proceeds.
   - Required/expected API keys (store with exact env var names):
     1. `GROQ_API_KEY` (required when `LLM_PROVIDER=groq` or when using Groq directly)
     2. `MISTRAL_API_KEY` (required when `LLM_PROVIDER=mistral`)
     3. `BRAVE_API_KEY` (required for `web-search` skill)
     4. `LANGFUSE_PUBLIC_KEY` (optional, tracing)
     5. `LANGFUSE_SECRET_KEY` (optional, tracing)
     6. `LANGSMITH_API_KEY` (optional, tracing)
5. Skill secret coverage:
   - `web-search` requires `BRAVE_API_KEY` (and will fail closed if missing).
6. Tooling permissions: CLI can read skill directories under `src/tools/skills/` and execute tool containers.
7. Network access: outbound network permissions for web research tools (when enabled).

## Behavior
1. If a required permission is missing, stop onboarding and print a clear remediation step.
2. If Docker is missing/unavailable but only optional tools need it, proceed and mark those tools as unavailable.
3. Persist the checklist result so subsequent runs can skip checks unless the environment changed.
