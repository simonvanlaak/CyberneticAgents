# Secrets Integration Notes

## Overview
This document summarizes the work done to integrate **1Password service accounts** into the CyberneticAgents workflow. The goal is to:
- Fetch secrets (e.g., `BRAVE_API_KEY`) from 1Password at runtime.
- Inject them into processes/containers as environment variables without persisting values.

---

## Key Insights

### 1. **1Password CLI Authentication**
- The `op` CLI requires authentication in non-interactive environments (e.g., Docker).
- **Service Account Tokens** are the recommended method for automation.
- **Reference Format**: `op://<VAULT_NAME>/<ITEM_NAME>/<FIELD_NAME>` (e.g., `op://CyberneticAgents/BRAVE_API_KEY/credential`).

### 2. **Tool Secret Mapping**
- Tool-specific secrets are hardcoded in the runtime as a dict:
  `TOOL_SECRET_ENV_VARS = {"web_search": ["BRAVE_API_KEY"]}`
- Users must name secrets in 1Password to match the required env var names.

### 3. **Runtime Injection (No Secret Persistence)**
- Prefer `op run` to inject secrets for the lifetime of a process.
- Avoid writing secrets to disk or committing `.env` files.
- If a file is unavoidable (e.g., Docker compose env file), create it in a temp dir and delete it immediately after use.

### 4. **Service Account Token Handling**
- Pass the service account token via environment injection (not inline on the command line).
- Avoid putting tokens in shell history or process lists.

---

## Current State

### What Works
- ✅ **Service Account Flow**: Service account tokens are supported for non-interactive auth.
- ✅ **Runtime Injection**: Secrets are injected into executor processes via env mapping.

### What Doesn’t Work
- ❌ **Secret Mapping Coverage**: Tool-to-secret mappings still need to be defined per tool.

---

## Proposed Workflow (Service Accounts)

### A. Set up 1Password Service Account
1. Create a 1Password service account with access to the CyberneticAgents vault.
2. Store tool secrets as items in 1Password using the exact env var names
   required by the runtime (e.g., `BRAVE_API_KEY`).
3. Use the `op://` reference format in config (never store secret values in repo).

### B. Local Dev (Recommended)
Use `op run` so secrets exist only for the process lifetime:
```bash
op run --env-file ./.env.example -- \
  python3 main.py
```
Note: `.env.example` contains only variable names, not values.

### C. Docker Run (Recommended)
Inject secrets into the host process via `op run`, then required env vars
are injected into the executor based on the hardcoded mapping.
```bash
op run --env-file ./.env.example -- \
  python3 main.py
```

---

## Next Steps

1. **Verify Tags in 1Password**:
   - Ensure secrets exist in the vault and are accessible to the service account.

2. **Test the Workflow**:
   ```bash
   op run --env-file ./.env.example -- \
     python3 main.py
   ```

---

## Files Modified
- `src/tools/cli_executor/Dockerfile.openclaw-tools`: Tools container definition.

---

## Lessons Learned
- **1Password CLI**: Requires explicit authentication in Docker (service accounts are best).
- **Secret Names**: Use exact env var names required by the runtime (e.g., `BRAVE_API_KEY`).
- **Permissions**: Only grant write access to required directories; use UID/GID mapping for Docker.
