"""Pytest worker identification helpers."""

from __future__ import annotations

from typing import Mapping


def get_pytest_worker_id(env: Mapping[str, str], pid: int) -> str:
    """
    Resolve a stable pytest worker identifier.

    Args:
        env: Environment mapping to read PYTEST_XDIST_WORKER from.
        pid: Process ID to use as fallback when xdist is not active.

    Returns:
        A worker identifier string.
    """
    worker = env.get("PYTEST_XDIST_WORKER")
    if worker:
        return worker
    return f"pid{pid}"
