from __future__ import annotations

import pytest

from src.cyberagent.cli import log_filters


def test_extract_log_level_bracketed() -> None:
    assert log_filters.extract_log_level("2024-01-01 [INFO] ready") == "INFO"


def test_extract_log_level_fallback() -> None:
    assert log_filters.extract_log_level("2024-01-01 00:00:00 ERROR boom") == "ERROR"


def test_extract_log_level_missing() -> None:
    assert log_filters.extract_log_level("short line") is None


def test_normalize_log_levels_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        log_filters._normalize_log_levels(["warn"])  # type: ignore[attr-defined]


def test_resolve_log_levels_invalid_returns_none() -> None:
    assert log_filters.resolve_log_levels(["warn"], default_to_errors=False) is None


def test_resolve_log_levels_defaults_to_errors_only() -> None:
    resolved = log_filters.resolve_log_levels(None, default_to_errors=True)
    assert resolved == {"ERROR", "CRITICAL"}


def test_resolve_log_levels_keeps_requested_levels() -> None:
    resolved = log_filters.resolve_log_levels(["info"], default_to_errors=False)
    assert resolved == {"INFO"}


def test_filter_logs_rejects_unknown_level_lines() -> None:
    lines = [
        "2024-01-01 00:00:00 NOTICE something",
        "2024-01-01 00:00:01 ERROR fail",
    ]
    filtered = log_filters.filter_logs(lines, None, 10, {"ERROR"})
    assert filtered == ["2024-01-01 00:00:01 ERROR fail"]
