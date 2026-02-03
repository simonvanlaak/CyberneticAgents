"""Observability helpers for memory operations."""

from __future__ import annotations

import json
import logging
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
    read_count: int = 0
    write_count: int = 0
    list_count: int = 0
    hit_count: int = 0
    miss_count: int = 0
    read_latency_ms_total: float = 0.0
    list_latency_ms_total: float = 0.0
    injection_size_total: int = 0

    def record_read(self, hit: bool) -> None:
        self.read_count += 1
        if hit:
            self.hit_count += 1
        else:
            self.miss_count += 1

    def record_write(self, count: int = 1) -> None:
        self.write_count += count

    def record_list(self) -> None:
        self.list_count += 1

    def record_read_latency(self, latency_ms: float) -> None:
        self.read_latency_ms_total += latency_ms

    def record_list_latency(self, latency_ms: float) -> None:
        self.list_latency_ms_total += latency_ms

    def record_injection_size(self, size: int) -> None:
        self.injection_size_total += size

    @property
    def hit_rate(self) -> float:
        total = self.hit_count + self.miss_count
        if total == 0:
            return 0.0
        return self.hit_count / total
