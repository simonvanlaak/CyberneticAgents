"""Observability helpers for memory operations."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Protocol

from src.cyberagent.memory.models import MemoryAuditEvent

logger = logging.getLogger(__name__)


class MemoryAuditSink(Protocol):
    """Sink for memory audit events."""

    def record(self, event: MemoryAuditEvent) -> None:
        """Record a memory audit event."""


@dataclass
class LoggingMemoryAuditSink:
    """Log memory audit events using the standard logger."""

    def record(self, event: MemoryAuditEvent) -> None:
        payload = json.dumps(
            {
                "action": event.action,
                "actor_id": event.actor_id,
                "scope": event.scope.value,
                "namespace": event.namespace,
                "resource_id": event.resource_id,
                "success": event.success,
                "timestamp": event.timestamp.isoformat(),
                "details": event.details,
            }
        )
        logger.info("memory_audit %s", payload)


@dataclass
class MemoryMetrics:
    reporter: "MemoryMetricsReporter | None" = None
    read_count: int = 0
    write_count: int = 0
    list_count: int = 0
    query_count: int = 0
    hit_count: int = 0
    miss_count: int = 0
    read_latency_ms_total: float = 0.0
    list_latency_ms_total: float = 0.0
    query_latency_ms_total: float = 0.0
    injection_size_total: int = 0

    def record_read(self, hit: bool) -> None:
        self.read_count += 1
        if hit:
            self.hit_count += 1
        else:
            self.miss_count += 1
        self._maybe_report()

    def record_write(self, count: int = 1) -> None:
        self.write_count += count
        self._maybe_report()

    def record_list(self) -> None:
        self.list_count += 1
        self._maybe_report()

    def record_query(self) -> None:
        self.query_count += 1
        self._maybe_report()

    def record_read_latency(self, latency_ms: float) -> None:
        self.read_latency_ms_total += latency_ms
        self._maybe_report()

    def record_list_latency(self, latency_ms: float) -> None:
        self.list_latency_ms_total += latency_ms
        self._maybe_report()

    def record_query_latency(self, latency_ms: float) -> None:
        self.query_latency_ms_total += latency_ms
        self._maybe_report()

    def record_injection_size(self, size: int) -> None:
        self.injection_size_total += size
        self._maybe_report()

    def _maybe_report(self) -> None:
        if self.reporter is None:
            return
        self.reporter.maybe_log(self)

    @property
    def hit_rate(self) -> float:
        total = self.hit_count + self.miss_count
        if total == 0:
            return 0.0
        return self.hit_count / total


@dataclass
class MemoryMetricsReporter:
    interval_seconds: float = 60.0
    _last_logged_at: float = 0.0

    def maybe_log(self, metrics: MemoryMetrics) -> None:
        now = time.monotonic()
        if (
            self.interval_seconds > 0
            and now - self._last_logged_at < self.interval_seconds
        ):
            return
        self._last_logged_at = now
        payload = {
            "read_count": metrics.read_count,
            "write_count": metrics.write_count,
            "list_count": metrics.list_count,
            "query_count": metrics.query_count,
            "hit_rate": metrics.hit_rate,
            "hit_count": metrics.hit_count,
            "miss_count": metrics.miss_count,
            "read_latency_ms_total": metrics.read_latency_ms_total,
            "list_latency_ms_total": metrics.list_latency_ms_total,
            "query_latency_ms_total": metrics.query_latency_ms_total,
            "injection_size_total": metrics.injection_size_total,
        }
        logger.info("memory_metrics %s", json.dumps(payload))


def build_memory_metrics() -> MemoryMetrics:
    enabled = os.environ.get("MEMORY_METRICS_LOG", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    if not enabled:
        return MemoryMetrics()
    interval_raw = os.environ.get("MEMORY_METRICS_LOG_INTERVAL_SECONDS", "60")
    try:
        interval = float(interval_raw)
    except ValueError as exc:
        raise ValueError(
            "MEMORY_METRICS_LOG_INTERVAL_SECONDS must be a number."
        ) from exc
    reporter = MemoryMetricsReporter(interval_seconds=interval)
    return MemoryMetrics(reporter=reporter)
