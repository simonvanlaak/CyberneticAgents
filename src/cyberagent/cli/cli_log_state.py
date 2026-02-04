from __future__ import annotations

import json
import os
import time
from pathlib import Path

from src.cyberagent.cli import log_filters


def check_recent_runtime_errors(
    *,
    command: str | None,
    logs_dir: Path,
    state_file: Path,
) -> None:
    if not logs_dir.exists():
        return
    log_files = sorted(logs_dir.glob("*.log"), key=os.path.getmtime)
    if not log_files:
        return
    latest_log = log_files[-1]
    state = _load_cli_log_state(state_file)
    offset = 0
    latest_path = str(latest_log.resolve())
    if state and state.get("log_path") == latest_path:
        offset = _safe_int(state.get("byte_offset"), 0)

    warnings = 0
    errors = 0
    try:
        with latest_log.open("rb") as handle:
            handle.seek(offset)
            new_bytes = handle.read()
            new_offset = handle.tell()
        if new_bytes:
            text = new_bytes.decode("utf-8", errors="ignore")
            for line in text.splitlines():
                level = log_filters.extract_log_level(line)
                if level == "WARNING":
                    warnings += 1
                elif level == "ERROR":
                    errors += 1
        _store_cli_log_state(state_file, latest_path, new_offset)
    except OSError:
        return

    if warnings or errors:
        from src.cyberagent.cli.message_catalog import get_message

        print(
            get_message(
                "cyberagent",
                "new_runtime_logs",
                errors=errors,
                warnings=warnings,
            )
        )


def _load_cli_log_state(state_file: Path) -> dict[str, object] | None:
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _store_cli_log_state(state_file: Path, log_path: str, byte_offset: int) -> None:
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "log_path": log_path,
            "byte_offset": byte_offset,
            "last_checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
