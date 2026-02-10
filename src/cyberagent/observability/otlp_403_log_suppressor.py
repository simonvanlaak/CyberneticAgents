# -*- coding: utf-8 -*-
"""Utilities for making OTLP exporter failures less noisy.

Background:
OpenTelemetry's OTLP HTTP trace exporter logs an ERROR every time an export fails.
When Langfuse ingestion is suspended (commonly an HTTP 403 with a quota/plan
message), this creates log spam that obscures real runtime issues.

This module installs a logging.Filter that:
- Detects "export failed" log records for HTTP 403/quota/suspension.
- Rate-limits identical errors to a configurable interval.
- Emits a single actionable warning per interval with guidance.

The exporter itself is left untouched; we only influence logging output.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Callable


_EXPORTER_LOGGER_NAME = "opentelemetry.exporter.otlp.proto.http.trace_exporter"


def _is_langfuse_ingestion_suspended_403(message: str) -> bool:
    msg = message.lower()
    if "failed to export span batch" not in msg:
        return False
    if "code: 403" not in msg and " 403" not in msg:
        return False

    # Heuristics: we only want to suppress quota/suspension noise, not auth
    # misconfigurations or other unexpected 403s.
    suspension_markers = [
        "ingestion suspended",
        "usage threshold",
        "forbiddenerror",
        "please upgrade",
        "quota",
    ]
    return any(m in msg for m in suspension_markers)


@dataclass
class _RateLimitState:
    last_allowed_ts: float | None = None


class OtlpLangfuse403RateLimitFilter(logging.Filter):
    """Rate-limit noisy OTLP exporter 403 errors.

    Args:
        interval_seconds: Minimum time between allowed exporter log records.
        now: Injectable time function for testability.
        guidance_logger: Logger used to emit a single actionable warning.
    """

    def __init__(
        self,
        interval_seconds: float,
        *,
        now: Callable[[], float] = time.time,
        guidance_logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self._interval_seconds = float(interval_seconds)
        self._now = now
        self._state = _RateLimitState()
        self._guidance_logger = guidance_logger or logging.getLogger(
            "cyberagent.observability"
        )

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 - logging API
        try:
            message = record.getMessage()
        except Exception:
            return True

        if not _is_langfuse_ingestion_suspended_403(message):
            return True

        ts = self._now()
        last = self._state.last_allowed_ts
        if last is not None and (ts - last) < self._interval_seconds:
            return False

        self._state.last_allowed_ts = ts

        # Downgrade to WARNING to avoid falsely signalling runtime failure.
        record.levelno = logging.WARNING
        record.levelname = logging.getLevelName(logging.WARNING)

        self._guidance_logger.warning(
            "Langfuse OTLP ingestion appears suspended (HTTP 403). "
            "Suppressing repeated exporter errors for %.0fs. "
            "To resolve: upgrade plan/increase quota or disable tracing by unsetting "
            "LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY (or point LANGFUSE_BASE_URL to a "
            "working Langfuse instance).",
            self._interval_seconds,
        )

        return True


def install_otlp_langfuse_403_log_suppression() -> None:
    """Install rate-limiting filter for Langfuse OTLP 403 exporter errors.

    Controlled by env var CYBERAGENT_OTLP_403_SUPPRESS_SECONDS (default: 300).
    Set to 0 to disable.
    """

    raw = os.environ.get("CYBERAGENT_OTLP_403_SUPPRESS_SECONDS", "300").strip()
    try:
        interval = float(raw)
    except ValueError:
        interval = 300.0

    if interval <= 0:
        return

    exporter_logger = logging.getLogger(_EXPORTER_LOGGER_NAME)

    # Avoid duplicate filters on repeated runtime initializations.
    for f in exporter_logger.filters:
        if isinstance(f, OtlpLangfuse403RateLimitFilter):
            return

    exporter_logger.addFilter(OtlpLangfuse403RateLimitFilter(interval_seconds=interval))
