# Agent CLI Interaction Requirements for CyberneticAgents

## Overview
The CyberneticAgents platform should expose a robust command‑line interface (CLI) that allows users and automated agents to interact programmatically with the system. This document outlines the functional and non‑functional requirements for the CLI.

## Functional Requirements

1. **Authentication & Authorization**
   - Support login via API token, OAuth2, or 1Password CLI integration.
   - Allow role‑based access control (admin, user, read‑only).
   - Provide a `logout` command to revoke local credentials.

2. **Core Commands**
   - `ca agents list` – List all registered agents with status, version, and tags.
   - `ca agents show <agent-id>` – Detailed view of a single agent.
   - `ca agents start <agent-id>` / `stop` – Control agent lifecycle.
   - `ca agents logs <agent-id> [--follow]` – Retrieve recent logs, optional live tail.
   - `ca agents config get/set <agent-id> <key> [value]` – Inspect or modify configuration.
   - `ca agents exec <agent-id> -- <command>` – Run arbitrary commands inside an agent’s container.
   - `ca jobs submit <definition.yaml>` – Submit a job definition for execution.
   - `ca jobs status <job-id>` – Query job progress and results.
   - `ca tasks schedule <cron|every|at> <payload>` – Create scheduled tasks.
   - `ca tasks list` – List scheduled tasks.
   - `ca tasks delete <task-id>` – Remove a scheduled task.

3. **Output Formats**
   - JSON (`--json`) for machine consumption.
   - Human‑readable tables (`--table`) as default.
   - Optional YAML (`--yaml`).

4. **Error Handling**
   - Consistent exit codes (0 success, 1 auth error, 2 validation, 3 execution failure, …).
   - Human‑friendly error messages with `--verbose` for stack traces.

5. **Scripting & Automation**
   - Provide a `--quiet` flag to suppress non‑essential output.
   - Allow chaining with standard shell pipelines.
   - Support environment variable interpolation for tokens and config values.

## Non‑Functional Requirements

- **Security**: All communication over HTTPS; secrets never written to stdout unless explicitly requested.
- **Performance**: Typical command latency < 500 ms for read‑only ops, < 2 s for actions that involve container orchestration.
- **Portability**: Works on Linux, macOS, and Windows (via WSL or native binary).
- **Extensibility**: Plug‑in architecture so new sub‑commands can be added without modifying the core binary.
- **Documentation**: Auto‑generated `--help` for each command and a markdown reference in the docs directory.
- **Testing**: Unit tests covering > 90 % of command paths, integration tests against a local dev cluster.

## Example Usage
```bash
# Authenticate using a 1Password secret
ca login --token $(op read "op://MyVault/CyberneticAgents/token")

# List agents in JSON for a script
ca agents list --json > agents.json

# Restart a specific agent and follow its logs
ca agents restart agent-42 && ca agents logs agent-42 --follow

# Schedule a daily health‑check task
ca tasks schedule every --everyMs 86400000 --payload '{"kind":"systemEvent","text":"Health check"}'
```

## Open Issues
- Decide on default token storage (keyring vs config file).
- Define schema for `definition.yaml` job specifications.
- Evaluate integration with the existing OpenClaw `sessions_spawn` mechanism for on‑demand agent runs.

---
*Document created by OpenClaw assistant on 2026‑01‑31.*