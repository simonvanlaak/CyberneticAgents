"""Session log ingestion and compaction."""

from __future__ import annotations

from dataclasses import dataclass
import re
import time

from src.cyberagent.memory.crud import (
    MemoryActorContext,
    MemoryCreateRequest,
    MemoryCrudService,
)
from src.cyberagent.memory.models import (
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.memory.pruning import MemoryPruner, MemoryPruningConfig
from src.cyberagent.memory.reflection import MemoryReflectionService
from src.cyberagent.memory.registry import StaticScopeRegistry

_REDACT_TOKEN = re.compile(r"[A-Za-z0-9_\-]{24,}")


@dataclass(frozen=True)
class MemorySessionConfig:
    max_log_chars: int = 2000
    compaction_threshold_chars: int = 8000
    reflection_interval_seconds: int = 3600
    max_entries_per_namespace: int = 1000


class MemorySessionRecorder:
    def __init__(
        self,
        *,
        registry: StaticScopeRegistry,
        reflection_service: MemoryReflectionService,
        config: MemorySessionConfig | None = None,
    ) -> None:
        self._registry = registry
        self._crud = MemoryCrudService(registry=registry)
        self._reflection = reflection_service
        self._config = config or MemorySessionConfig()
        self._pruner = MemoryPruner(
            registry=registry,
            config=MemoryPruningConfig(
                max_entries_per_namespace=self._config.max_entries_per_namespace
            ),
        )
        self._buffers: dict[str, list[str]] = {}
        self._last_reflection: dict[str, float] = {}

    def record(
        self,
        *,
        actor: MemoryActorContext,
        scope: MemoryScope,
        namespace: str,
        logs: list[str],
    ) -> None:
        if not logs:
            return
        sanitized = [self._sanitize(line) for line in logs if line.strip()]
        if not sanitized:
            return
        content = "\n".join(sanitized)
        if len(content) > self._config.max_log_chars:
            content = f"{content[: self._config.max_log_chars]}..."
        request = MemoryCreateRequest(
            content=content,
            namespace=namespace,
            scope=scope,
            tags=["session_log"],
            priority=MemoryPriority.LOW,
            source=MemorySource.TOOL,
            confidence=0.4,
            expires_at=None,
            layer=MemoryLayer.SESSION,
            owner_agent_id=actor.agent_id,
        )
        self._crud.create_entries(actor=actor, requests=[request])
        self._pruner.prune(actor=actor, scope=scope, namespace=namespace)
        self._append_buffer(
            actor=actor, scope=scope, namespace=namespace, logs=sanitized
        )

    def _append_buffer(
        self,
        *,
        actor: MemoryActorContext,
        scope: MemoryScope,
        namespace: str,
        logs: list[str],
    ) -> None:
        key = f"{actor.agent_id}:{scope.value}:{namespace}"
        buffer = self._buffers.setdefault(key, [])
        buffer.extend(logs)
        total_chars = sum(len(entry) for entry in buffer)
        now = time.time()
        last = self._last_reflection.get(key, 0.0)
        if total_chars >= self._config.compaction_threshold_chars or (
            now - last >= self._config.reflection_interval_seconds
        ):
            self._reflection.reflect_and_store(
                actor=actor,
                scope=scope,
                namespace=namespace,
                session_logs=buffer,
                layer=MemoryLayer.LONG_TERM,
            )
            self._buffers[key] = []
            self._last_reflection[key] = now

    @staticmethod
    def _sanitize(text: str) -> str:
        return _REDACT_TOKEN.sub("[REDACTED]", text.strip())
