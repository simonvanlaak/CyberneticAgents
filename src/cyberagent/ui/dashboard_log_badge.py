from __future__ import annotations

from pathlib import Path

from src.cyberagent.cli import log_filters
from src.cyberagent.cli.log_session import get_session_log_files


def count_warnings_errors(logs_dir: Path) -> tuple[int, int]:
    """
    Count WARNING and ERROR lines across runtime logs in the active session.
    """
    log_files = get_session_log_files(logs_dir)
    if not log_files:
        return 0, 0
    warnings = 0
    errors = 0

    for log_file in log_files:
        try:
            text = log_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            level = log_filters.extract_log_level(line)
            if level == "WARNING":
                warnings += 1
            elif level == "ERROR":
                errors += 1
    return warnings, errors
