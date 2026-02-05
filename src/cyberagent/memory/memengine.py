"""MemEngine-style adapter for memory operations."""

from __future__ import annotations

from dataclasses import dataclass
import time

from src.cyberagent.memory.crud import MemoryActorContext
from src.cyberagent.memory.models import (
    MemoryLayer,
    MemoryListResult,
    MemoryQuery,
    MemoryScope,
)
from src.cyberagent.memory.observability import MemoryMetrics
from src.cyberagent.memory.permissions import MemoryAction, check_memory_permission
from src.cyberagent.memory.registry import StaticScopeRegistry


@dataclass(frozen=True)
class MemEngineConfig:
    max_summary_chars: int = 1200


class MemEngine:
    """Minimal MemEngine adapter over registry-backed stores."""

    def __init__(
        self,
        *,
        registry: StaticScopeRegistry,
        metrics: MemoryMetrics | None = None,
        config: MemEngineConfig | None = None,
    ) -> None:
        self._registry = registry
        self._metrics = metrics
        self._config = config or MemEngineConfig()

    def search_entries(
        self,
        *,
        actor: MemoryActorContext,
        scope: MemoryScope,
        namespace: str,
        query_text: str | None,
        limit: int,
        cursor: str | None = None,
        tags: list[str] | None = None,
        layer: MemoryLayer | None = None,
    ) -> MemoryListResult:
        self._require_permission(actor=actor, scope=scope)
        owner_agent_id = actor.agent_id if scope == MemoryScope.AGENT else None
        query = MemoryQuery(
            text=query_text,
            scope=scope,
            namespace=namespace,
            limit=limit,
            cursor=cursor,
            tags=tags,
            layer=layer,
            owner_agent_id=owner_agent_id,
        )
        store = self._registry.resolve(scope)
        start = time.perf_counter()
        result = store.query(query)
        if self._metrics:
            self._metrics.record_query_latency((time.perf_counter() - start) * 1000)
            self._metrics.record_query()
        return result

    def summarize(self, entries: list[str]) -> str:
        joined = " ".join(entry.strip() for entry in entries if entry.strip())
        if len(joined) <= self._config.max_summary_chars:
            return joined
        return f"{joined[:self._config.max_summary_chars]}..."

    @staticmethod
    def _require_permission(*, actor: MemoryActorContext, scope: MemoryScope) -> None:
        allowed = check_memory_permission(
            actor_team_id=actor.team_id,
            target_team_id=actor.team_id,
            system_type=actor.system_type,
            scope=scope,
            action=MemoryAction.READ,
        )
        if not allowed:
            raise PermissionError(
                "Memory access denied for "
                f"scope={scope.value} system_type={actor.system_type.value}"
            )
