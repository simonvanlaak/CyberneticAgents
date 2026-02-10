# -*- coding: utf-8 -*-

from __future__ import annotations

import logging

from src.cyberagent.observability.otlp_403_log_suppressor import (
    OtlpLangfuse403RateLimitFilter,
)


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def now(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def _make_record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="opentelemetry.exporter.otlp.proto.http.trace_exporter",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_allows_first_403_then_suppresses_until_interval_expires() -> None:
    clock = _FakeClock()

    guidance_logger = logging.getLogger("test.guidance")
    guidance_logger.setLevel(logging.WARNING)
    captured: list[str] = []

    handler = logging.StreamHandler()
    handler.emit = lambda record: captured.append(record.getMessage())  # type: ignore[method-assign]
    guidance_logger.handlers = [handler]
    guidance_logger.propagate = False

    filt = OtlpLangfuse403RateLimitFilter(
        interval_seconds=60.0,
        now=clock.now,
        guidance_logger=guidance_logger,
    )

    rec1 = _make_record(
        "Failed to export span batch code: 403. "
        "Reason payload: {\"message\":\"Ingestion suspended: Usage threshold exceeded\"}"
    )
    assert filt.filter(rec1) is True
    assert rec1.levelno == logging.WARNING
    assert len(captured) == 1

    rec2 = _make_record(
        "Failed to export span batch code: 403. "
        "Reason payload: {\"message\":\"Ingestion suspended: Usage threshold exceeded\"}"
    )
    assert filt.filter(rec2) is False
    assert len(captured) == 1

    clock.advance(61.0)

    rec3 = _make_record(
        "Failed to export span batch code: 403. "
        "Reason payload: {\"message\":\"Ingestion suspended: Usage threshold exceeded\"}"
    )
    assert filt.filter(rec3) is True
    assert rec3.levelno == logging.WARNING
    assert len(captured) == 2


def test_does_not_suppress_non_suspension_messages() -> None:
    clock = _FakeClock()
    filt = OtlpLangfuse403RateLimitFilter(interval_seconds=60.0, now=clock.now)

    rec = _make_record("Failed to export span batch code: 500")
    assert filt.filter(rec) is True
    assert rec.levelno == logging.ERROR
