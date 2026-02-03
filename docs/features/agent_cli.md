# Agent CLI Feature

## Overview
The CyberneticAgents CLI provides a thin, user-focused interface for operating the VSM runtime. It avoids direct system mutation, instead routing user intent through System4 via `suggest`, and exposes read-only status and observability commands.

## Core Commands
- **start**: `cyberagent start` boots the runtime in the background.
- **stop**: `cyberagent stop` shuts down the runtime.
- **status**: `cyberagent status` renders the current team/system/strategy/task hierarchy.
  - `--team <id>` scopes to a specific team.
  - `--active-only` limits output to active systems.
  - `--json` emits machine-readable JSON.
- **suggest**: `cyberagent suggest "<message>"` sends a suggestion payload to System4.
  - `--payload` / `--file` supports inline JSON/YAML payloads.
- **inbox**: `cyberagent inbox` shows shared inbox entries (user prompts, system questions, system responses).
  - `--answered` includes answered system questions.
- **watch**: `cyberagent watch` polls the shared inbox until interrupted.
- **logs**: `cyberagent logs` prints recent runtime logs.
  - `--filter` substring filter, `--level` and `--errors` for log levels.
  - `--follow` tails logs in real time.
- **config view**: `cyberagent config view` shows registered teams/systems (read-only).
- **login**: `cyberagent login` stores a token in the OS keyring (or a local fallback file).
- **onboarding**: `cyberagent onboarding` creates the default root team if none exists.
- **dev**: `cyberagent dev ...` exposes developer-only commands.
  - `system-run <system_id> "<message>"` sends a one-off message to a system.
  - `tool-test <tool_name>` executes a skill tool directly.

## Runtime Behavior
- **Suggest-only**: the CLI does not mutate system state directly; System4 decides how to act.
- **Background runtime**: `start` spawns a background process and writes a PID file under `logs/`.
- **Logs summary**: each command prints a warning/error summary if new runtime logs were added since the last command.

## Output Formats
- Human-readable text by default.
- JSON output is available for `status` via `--json`.
- YAML output is not currently supported.

## Operational Notes
- `onboarding` sets up `default_team`, which the system treats as the root team.
- `dev` commands are intended for local debugging and should not be used in production workflows.

## File Map
- CLI entrypoint: `src/cyberagent/cli/cyberagent.py`
- Headless runtime: `src/cyberagent/cli/headless.py`
- Status rendering: `src/cyberagent/cli/status.py`
- CLI inbox/session: `src/cli_session.py`
- Shared inbox storage: `src/cyberagent/channels/inbox.py`
- Logs: `logs/` directory

## How to Test
- `python3 -m pytest tests/cli/test_cyberagent.py -v`
- `python3 -m pytest tests/cli/test_status_cli.py -v`
