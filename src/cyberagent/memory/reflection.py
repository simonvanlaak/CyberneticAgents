"""Reflection helpers for memory summarization."""

from __future__ import annotations

from dataclasses import dataclass

from src.cyberagent.memory.crud import (
    MemoryActorContext,
    MemoryCreateRequest,
    MemoryCrudService,
)
from src.cyberagent.memory.memengine import MemEngine
from src.cyberagent.memory.models import (
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.memory.registry import StaticScopeRegistry


@dataclass(frozen=True)
class MemoryReflectionConfig:
    max_chars: int = 1200


class MemoryReflectionService:
    """Summarize session logs into memory entries."""

    def __init__(
        self,
        *,
        registry: StaticScopeRegistry,
        config: MemoryReflectionConfig | None = None,
        engine: MemEngine | None = None,
    ) -> None:
        self._registry = registry
        self._config = config or MemoryReflectionConfig()
        self._crud = MemoryCrudService(registry=registry)
        self._engine = engine

    def reflect_and_store(
        self,
        *,
        actor: MemoryActorContext,
        scope: MemoryScope,
        namespace: str,
        session_logs: list[str],
        layer: MemoryLayer,
    ):
        if not session_logs:
            return None
        if self._engine is None:
            summary = _summarize(session_logs, max_chars=self._config.max_chars)
        else:
            summary = self._engine.summarize(session_logs)
        request = MemoryCreateRequest(
            content=summary,
            namespace=namespace,
            scope=scope,
            tags=["reflection"],
            priority=MemoryPriority.MEDIUM,
            source=MemorySource.REFLECTION,
            confidence=0.6,
            expires_at=None,
            layer=layer,
            owner_agent_id=actor.agent_id,
        )
        created = self._crud.create_entries(actor=actor, requests=[request])
        return created[0] if created else None


def _summarize(entries: list[str], *, max_chars: int) -> str:
    joined = " ".join(entry.strip() for entry in entries if entry.strip())
    if len(joined) <= max_chars:
        return joined
    return f"{joined[:max_chars]}..."
