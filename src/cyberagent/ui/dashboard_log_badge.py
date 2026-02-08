from __future__ import annotations

import os
from pathlib import Path

from src.cyberagent.cli import log_filters


def count_warnings_errors(logs_dir: Path) -> tuple[int, int]:
    """
    Count WARNING and ERROR lines in the latest runtime log file.
    """
    if not logs_dir.exists():
        return 0, 0
    log_files = sorted(logs_dir.glob("*.log"), key=os.path.getmtime)
    if not log_files:
        return 0, 0

    latest_log = log_files[-1]
    warnings = 0
    errors = 0
    try:
        text = latest_log.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0, 0

    for line in text.splitlines():
        level = log_filters.extract_log_level(line)
        if level == "WARNING":
            warnings += 1
        elif level == "ERROR":
            errors += 1
    return warnings, errors
