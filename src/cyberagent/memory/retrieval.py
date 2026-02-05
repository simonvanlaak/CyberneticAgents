"""Memory retrieval and prompt injection helpers."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Iterable

from src.cyberagent.memory.crud import MemoryActorContext
from src.cyberagent.memory.memengine import MemEngine
from src.cyberagent.memory.models import (
    MemoryAuditEvent,
    MemoryEntry,
    MemoryLayer,
    MemoryQuery,
    MemoryScope,
)
from src.cyberagent.memory.observability import MemoryAuditSink, MemoryMetrics
from src.cyberagent.memory.permissions import MemoryAction, check_memory_permission
from src.cyberagent.memory.registry import StaticScopeRegistry


@dataclass(frozen=True)
class MemoryInjectionConfig:
    max_chars: int = 1200
    per_entry_max_chars: int = 400


class MemoryInjector:
    """Compress and format memory entries for prompt injection."""

    def __init__(
        self,
        *,
        config: MemoryInjectionConfig | None = None,
        metrics: MemoryMetrics | None = None,
    ) -> None:
        self._config = config or MemoryInjectionConfig()
        self._metrics = metrics

    def build_prompt_entries(self, entries: Iterable[MemoryEntry]) -> list[str]:
        max_chars = self._config.max_chars
        per_entry = self._config.per_entry_max_chars
        output: list[str] = []
        total = 0
        for entry in entries:
            content = entry.content.strip().replace("\n", " ")
            header = f"[{entry.scope.value}:{entry.namespace}|{entry.id}] "
            available = max_chars - total - len(header)
            if available <= 0:
                break
            max_content = min(per_entry, available)
            if len(content) > max_content:
                suffix = "..." if max_content > 3 else ""
                trim = max_content - len(suffix)
                content = f"{content[:trim]}{suffix}"
            line = f"{header}{content}"
            output.append(line)
            total += len(line)
        if self._metrics:
            self._metrics.record_injection_size(total)
        return output


class MemoryRetrievalService:
    """Retrieve memory entries with permission checks."""

    def __init__(
        self,
        *,
        registry: StaticScopeRegistry,
        metrics: MemoryMetrics | None = None,
        default_limit: int = 10,
        engine: MemEngine | None = None,
        audit_sink: MemoryAuditSink | None = None,
    ) -> None:
        self._registry = registry
        self._metrics = metrics
        self._default_limit = default_limit
        self._engine = engine
        self._audit_sink = audit_sink

    def search_entries(
        self,
        *,
        actor: MemoryActorContext,
        scope: MemoryScope,
        namespace: str,
        query_text: str | None,
        limit: int | None = None,
        cursor: str | None = None,
        tags: list[str] | None = None,
        layer: MemoryLayer | None = None,
        target_team_id: int | None = None,
    ):
        resolved_limit = limit or self._default_limit
        if self._engine is not None:
            result = self._engine.search_entries(
                actor=actor,
                scope=scope,
                namespace=namespace,
                query_text=query_text,
                limit=resolved_limit,
                cursor=cursor,
                tags=tags,
                layer=layer,
            )
            self._record_audit(
                actor=actor, scope=scope, namespace=namespace, result=result
            )
            return result
        self._require_permission(
            actor=actor, scope=scope, target_team_id=target_team_id
        )
        owner_agent_id = actor.agent_id if scope == MemoryScope.AGENT else None
        query = MemoryQuery(
            text=query_text,
            scope=scope,
            namespace=namespace,
            limit=resolved_limit,
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
        self._record_audit(actor=actor, scope=scope, namespace=namespace, result=result)
        return result

    def _record_audit(
        self,
        *,
        actor: MemoryActorContext,
        scope: MemoryScope,
        namespace: str,
        result,
    ) -> None:
        if not self._audit_sink:
            return
        for entry in result.items:
            event = MemoryAuditEvent(
                action="memory_retrieval",
                actor_id=actor.agent_id,
                scope=scope,
                namespace=namespace,
                resource_id=entry.id,
                success=True,
                details={},
            )
            self._audit_sink.record(event)

    @staticmethod
    def _require_permission(
        *,
        actor: MemoryActorContext,
        scope: MemoryScope,
        target_team_id: int | None,
    ) -> None:
        allowed = check_memory_permission(
            actor_team_id=actor.team_id,
            target_team_id=target_team_id or actor.team_id,
            system_type=actor.system_type,
            scope=scope,
            action=MemoryAction.READ,
        )
        if not allowed:
            raise PermissionError(
                "Memory access denied for "
                f"scope={scope.value} system_type={actor.system_type.value}"
            )
