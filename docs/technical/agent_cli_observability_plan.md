# Agent CLI Observability Plan (First Pass)

## Purpose
Add a lightweight, automatic signal in the CLI that surfaces new runtime warnings/errors since the last CLI command, without spamming normal output. Users can then run `cyberagent logs` for details.

## Goals
- Every CLI command checks whether new warnings/errors were logged since the last CLI command.
- If new items exist, print a short summary and a suggestion to use `cyberagent logs`.
- Use existing file-based logs (`logs/*.log`) and avoid external dependencies.
- Do not leak secrets to stdout.

## Non-Goals
- Real-time streaming or background notifications.
- Structured log ingestion pipeline.
- Changing the log format in this first pass.

## Current State (Verified)
- Runtime logs are written by `configure_autogen_logging()` in `src/cyberagent/core/logging.py` with a line format:
  - `YYYY-MM-DD HH:MM:SS.mmm LEVEL [logger] message`
- `cyberagent logs` reads the newest `logs/*.log` file and prints lines (optionally filtered).
- CLI commands do not currently surface new runtime errors automatically.

## Proposed Design
### 1) Track last-seen log position
- Store a small state file (e.g., `logs/cli_last_seen.json`).
- Contents:
  - `log_path`: absolute path to the log file last read.
  - `byte_offset`: last read byte position.
  - `last_checked_at`: ISO timestamp (optional, informational).

### 2) On every CLI command
- Before executing the command, run a lightweight check:
  1. Find latest log file (same logic as `cyberagent logs`).
  2. Load state file if present.
  3. If the latest log file changed, reset `byte_offset` to 0.
  4. Seek to `byte_offset` and read new lines.
  5. Count new lines with level `WARNING` or `ERROR`.
  6. If count > 0, print a summary:
     - Example: `New runtime logs since last command: 3 warnings, 1 error. Run 'cyberagent logs' to view.`
  7. Update `byte_offset` to current EOF and write state file.

### 3) Parsing rule
- Parse log level by splitting the line on spaces:
  - Level token is the 3rd token: `YYYY-MM-DD`, `HH:MM:SS.mmm`, `LEVEL`.
- Only count `WARNING` and `ERROR`.
- If parsing fails, ignore the line.

### 4) Where to hook
- Centralize in `src/cyberagent/cli/cyberagent.py`:
  - Add a helper like `_check_recent_runtime_errors()`.
  - Call it early in `main()` after parsing args, before dispatching the command handler.
- Keep the hook opt-out for commands that are already log-specific (e.g., `cyberagent logs`).

### 5) UX
- Make the message single-line, no stack traces.
- Never print log contents directly in the summary.
- Keep the CLI output stable for scripts:
  - If needed, add `--quiet` to suppress the summary (optional in phase 2).

## Edge Cases
- No `logs/` directory: skip silently.
- No log files: skip silently.
- Log rotation: detect a new log file and reset offset.
- Large logs: read incrementally from the offset only.

## Tests (TDD)
- Unit test for parsing levels from log lines.
- Unit test for state-file behavior when log file changes.
- Unit test ensuring `cyberagent logs` does not trigger a summary (if we opt out).

## Security
- Never output raw log lines in the summary.
- Avoid writing sensitive data to the state file.

## Incremental Phases
1. Phase 1 (this plan): offset-based summary on every CLI command.
2. Phase 2: richer `cyberagent logs` filters (`--level`, `--since`, `--agent`).
3. Phase 3: optional `--quiet` mode for CI and scripts.
