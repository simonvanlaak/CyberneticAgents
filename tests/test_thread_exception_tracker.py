from __future__ import annotations

from types import SimpleNamespace
import threading

import pytest

from src.cyberagent.testing.thread_exceptions import ThreadExceptionTracker


def test_thread_exception_tracker_records_exceptions() -> None:
    tracker = ThreadExceptionTracker()
    exc: BaseException | None = None

    try:
        raise ValueError("boom")
    except ValueError as caught:
        exc = caught

    assert exc is not None
    args = SimpleNamespace(
        thread=threading.Thread(name="worker-1"),
        exc_type=type(exc),
        exc_value=exc,
        exc_traceback=exc.__traceback__,
    )

    tracker.handle(args)

    assert tracker.count == 1
    assert "worker-1" in tracker.summary()


def test_thread_exception_tracker_raise_if_any() -> None:
    tracker = ThreadExceptionTracker()
    args = SimpleNamespace(
        thread=threading.Thread(name="worker-2"),
        exc_type=RuntimeError,
        exc_value=RuntimeError("fail"),
        exc_traceback=None,
    )

    tracker.handle(args)

    with pytest.raises(RuntimeError, match="Background thread exceptions"):
        tracker.raise_if_any()
