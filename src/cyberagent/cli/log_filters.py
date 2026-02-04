"""Helpers for filtering and parsing log output."""

from __future__ import annotations

from typing import Sequence


def filter_logs(
    lines: Sequence[str],
    pattern: str | None,
    limit: int,
    levels: set[str] | None,
) -> Sequence[str]:
    filtered = [line for line in lines if _matches_filter(line, pattern, levels)]
    return filtered[-limit:]


def resolve_log_levels(
    level_args: Sequence[str] | None, errors_only: bool
) -> set[str] | None:
    try:
        levels = _normalize_log_levels(level_args)
    except ValueError:
        return None
    if errors_only:
        error_levels = {"ERROR", "CRITICAL"}
        if levels is None:
            return error_levels
        return levels | error_levels
    return levels


def extract_log_level(line: str) -> str | None:
    for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        if f"[{level}]" in line:
            return level
    parts = line.split(" ", 3)
    if len(parts) < 3:
        return None
    level = parts[2].strip()
    return level if level else None


def _matches_filter(line: str, pattern: str | None, levels: set[str] | None) -> bool:
    if pattern is None:
        text_match = True
    else:
        text_match = pattern.lower() in line.lower()
    if not text_match:
        return False
    if levels is None:
        return True
    level = extract_log_level(line)
    if level is None:
        return False
    return level.upper() in levels


def _normalize_log_levels(level_args: Sequence[str] | None) -> set[str] | None:
    if not level_args:
        return None
    allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    normalized: set[str] = set()
    for arg in level_args:
        for raw in arg.split(","):
            token = raw.strip().upper()
            if not token:
                continue
            if token not in allowed:
                raise ValueError(f"Unknown log level: {token}")
            normalized.add(token)
    return normalized
