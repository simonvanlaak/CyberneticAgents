# Secret Management Feature

## Overview
CyberneticAgents uses 1Password service accounts to retrieve tool and runtime secrets at execution time. Secrets are never written to disk and are injected only into the tool execution environment.

## Core Capabilities
- **Service account auth**: Secrets require `OP_SERVICE_ACCOUNT_TOKEN` in the environment.
- **Tool mapping**: Tools declare required env vars via a central mapping in `secrets.py`.
- **On-demand resolution**: Missing env vars are resolved from 1Password using the item name and `credential` field.
- **Ephemeral injection**: Secrets are passed to the CLI executor environment for the duration of the tool run only.

## Runtime Behavior
- **Execution path**: `CliTool.execute()` calls `secrets.get_tool_secrets()` to resolve required values.
- **Failure mode**: If a required secret cannot be resolved, tool execution fails closed with an explicit error.
- **No persistence**: Secrets are not stored in files or written into the repository.

## 1Password Requirements
- Export `OP_SERVICE_ACCOUNT_TOKEN` before running the CLI.
- Store secrets as items in the `CyberneticAgents` vault.
- Use the secret’s env var name as the item title.
- Store the secret value in the `credential` field.

## Tool Mapping
Current tool-to-secret mapping lives in:
- `src/cyberagent/tools/cli_executor/secrets.py`

Example (web search):
- Tool: `web_search`
- Required env: `BRAVE_API_KEY`

## File Map
- Secret resolution: `src/cyberagent/tools/cli_executor/secrets.py`
- CLI executor: `src/cyberagent/tools/cli_executor/cli_tool.py`
- Onboarding checks: `src/cyberagent/cli/onboarding.py`

## How to Test
- `python3 -m pytest tests/tools/test_cli_tool_secrets.py -v`
- `python3 -m pytest tests/tools/test_cli_executor_coverage.py -v`
