from __future__ import annotations

import os
from pathlib import Path


def get_session_log_files(logs_dir: Path) -> list[Path]:
    """
    Return runtime log files for the active runtime session.

    Session boundary is derived from `cyberagent.pid` mtime when available.
    If no active PID marker exists, fall back to the latest log file.
    """
    if not logs_dir.exists():
        return []
    log_files = sorted(logs_dir.glob("*.log"), key=os.path.getmtime)
    if not log_files:
        return []

    pid_file = logs_dir / "cyberagent.pid"
    if pid_file.exists():
        try:
            session_start = pid_file.stat().st_mtime
        except OSError:
            session_start = None
        if session_start is not None:
            session_logs: list[Path] = []
            for log_file in log_files:
                try:
                    log_mtime = log_file.stat().st_mtime
                except OSError:
                    continue
                if log_mtime >= session_start:
                    session_logs.append(log_file)
            if session_logs:
                return session_logs

    return [log_files[-1]]
