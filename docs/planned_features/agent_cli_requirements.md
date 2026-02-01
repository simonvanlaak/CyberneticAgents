# Agent CLI Interaction Requirements for CyberneticAgents

## Purpose
The CLI is intended to make **agentic engineering of the Viable System Model (VSM)** as simple and transparent as possible. It should provide a thin, user‑focused interface that delegates all system‑level actions (entity creation, policy management, direct agent control) to the VSM itself. The CLI only **suggests** actions to the VSM (system4) and reports on system activity.

## Core Functional Requirements

1. **Start / Stop the VSM**
   - `cyberagent start` – Boot the VSM runtime.
   - `cyberagent stop` – Gracefully shut down the VSM.
   - `cyberagent status` – Show current state (running, stopped, errors) **and** display the VSM’s purpose, strategy, current initiative, and top‑level task summary.


2. **Messaging with system4**
   - `cyberagent suggest <json|yaml>` – Send a suggestion payload to system4. The payload describes a desired change (e.g., create an agent, modify a policy) but **does not execute it directly**.
   - `cyberagent inbox` – Pull pending messages addressed to the CLI user from system4. This is a pull‑based command; no background notification service is required.
   - `cyberagent watch` – Continuously poll `inbox` and stream new messages until interrupted (useful for live monitoring during development).

3. **Observability / Logging**
   - `cyberagent logs` – Show a chronological view of all inter‑agent messages processed by the VSM, with timestamps, source, destination, and payload details.
   - `cyberagent logs --filter <criteria>` – Filter logs by agent, message type, or time range.
   - `cyberagent logs --follow` – Tail logs in real time, similar to `tail -f`.

4. **Configuration (Read‑Only)**
   - `cyberagent config view` – Display the current VSM configuration of systems (read‑only). Editing is prohibited; changes must be proposed via `cyberagent suggest`.

5. **Output Formats**
   - Default human‑readable tables.
   - `--json` for machine‑friendly consumption.
   - `--yaml` optional for compatibility with existing VSM specs.

## Non‑Functional Requirements

- **Security**: All CLI‑to‑VSM communication occurs over TLS. Authentication is performed once via `cyberagent login` (token stored securely in the OS keyring). No secrets are ever written to stdout.
- **Performance**: Commands return within 300 ms for read‑only queries; start/stop operations may take up to a few seconds.
- **Portability**: Works on Linux, macOS, and Windows (via WSL or native binary).
- **Simplicity**: Minimal set of commands focused on the workflow described above; no hidden side‑effects.
- **Extensibility**: Plug‑in architecture allowing future commands that still respect the “suggest‑only” principle.
- **Documentation**: Each command provides `--help`; a full markdown reference lives in this docs directory.
- **Testing**: Unit tests cover > 90 % of command paths; integration tests verify end‑to‑end interaction with a local VSM instance.

## Example Usage
```bash
# Start the VSM
ca vsm start

# Propose creation of a new monitoring agent (system4 will decide)
cat <<EOF | ca suggest --json
{
  "action": "create_agent",
  "spec": {
    "name": "monitor",
    "type": "observer",
    "config": {"interval": "5s"}
  }
}
EOF

# Check for responses from system4
cyberagent inbox

# Watch live messages while developing
cyberagent watch

# Inspect inter‑agent traffic logs
cyberagent logs --follow
```

## Open Issues
- Define the exact schema for suggestion payloads accepted by system4.
- Determine the polling interval for `cyberagent inbox` and `cyberagent watch` (configurable?).
- Clarify how error handling and retry logic should be exposed to the CLI user.

---
*Document updated by OpenClaw assistant on 2026‑01‑31.*
