"""Memory CRUD service layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Iterable, Sequence
from uuid import uuid4

from src.cyberagent.memory.models import (
    MemoryAuditEvent,
    MemoryEntry,
    MemoryListResult,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.memory.observability import MemoryAuditSink, MemoryMetrics
from src.cyberagent.memory.permissions import MemoryAction, check_memory_permission
from src.cyberagent.memory.registry import StaticScopeRegistry
from src.enums import SystemType


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class MemoryActorContext:
    agent_id: str
    system_id: int
    team_id: int
    system_type: SystemType


@dataclass(slots=True)
class MemoryCreateRequest:
    content: str
    namespace: str
    scope: MemoryScope | None
    tags: list[str] | None
    priority: MemoryPriority
    source: MemorySource
    confidence: float
    expires_at: datetime | None
    owner_agent_id: str | None = None
    entry_id: str | None = None
    target_team_id: int | None = None


@dataclass(slots=True)
class MemoryReadRequest:
    entry_id: str
    scope: MemoryScope | None
    namespace: str
    target_team_id: int | None = None


@dataclass(slots=True)
class MemoryUpdateRequest:
    entry_id: str
    scope: MemoryScope | None
    namespace: str
    content: str | None = None
    tags: list[str] | None = None
    priority: MemoryPriority | None = None
    confidence: float | None = None
    expires_at: datetime | None = None
    target_team_id: int | None = None


@dataclass(slots=True)
class MemoryDeleteRequest:
    entry_id: str
    scope: MemoryScope | None
    namespace: str
    target_team_id: int | None = None


class MemoryCrudService:
    """Memory CRUD operations with scope defaults and permission checks."""

    def __init__(
        self,
        *,
        registry: StaticScopeRegistry,
        max_bulk_items: int = 10,
        default_scope: MemoryScope = MemoryScope.AGENT,
        default_page_size: int = 25,
        max_page_size: int = 100,
        metrics: MemoryMetrics | None = None,
        audit_sink: MemoryAuditSink | None = None,
    ) -> None:
        self._registry = registry
        self._max_bulk_items = max_bulk_items
        self._default_scope = default_scope
        self._default_page_size = default_page_size
        self._max_page_size = max_page_size
        self._metrics = metrics
        self._audit_sink = audit_sink

    def create_entries(
        self, *, actor: MemoryActorContext, requests: Sequence[MemoryCreateRequest]
    ) -> list[MemoryEntry]:
        self._validate_bulk_size(requests)
        created: list[MemoryEntry] = []
        for request in requests:
            scope = request.scope or self._default_scope
            target_team_id = self._resolve_target_team_id(
                actor, scope, request.target_team_id
            )
            self._require_permission(
                actor=actor,
                scope=scope,
                action=MemoryAction.WRITE,
                target_team_id=target_team_id,
            )
            owner_agent_id = request.owner_agent_id or actor.agent_id
            self._require_owner_match(scope, actor.agent_id, owner_agent_id)
            now = _utc_now()
            entry = MemoryEntry(
                id=request.entry_id or uuid4().hex,
                scope=scope,
                namespace=request.namespace,
                owner_agent_id=owner_agent_id,
                content=request.content,
                tags=list(request.tags or []),
                priority=request.priority,
                created_at=now,
                updated_at=now,
                expires_at=request.expires_at,
                source=request.source,
                confidence=request.confidence,
            )
            store = self._registry.resolve(scope)
            created_entry = store.add(entry)
            created.append(created_entry)
            self._record_write(count=1)
            self._record_audit(
                actor=actor,
                scope=scope,
                namespace=request.namespace,
                resource_id=created_entry.id,
                action="memory_create",
                success=True,
                details={"source": request.source.value},
            )
        return created

    def read_entry(
        self, *, actor: MemoryActorContext, request: MemoryReadRequest
    ) -> MemoryEntry | None:
        scope = request.scope or self._default_scope
        target_team_id = self._resolve_target_team_id(
            actor, scope, request.target_team_id
        )
        self._require_permission(
            actor=actor,
            scope=scope,
            action=MemoryAction.READ,
            target_team_id=target_team_id,
        )
        store = self._registry.resolve(scope)
        start = time.perf_counter()
        entry = store.get(request.entry_id, scope, request.namespace)
        self._record_read_latency((time.perf_counter() - start) * 1000)
        if entry is None:
            self._record_read(hit=False)
            self._record_audit(
                actor=actor,
                scope=scope,
                namespace=request.namespace,
                resource_id=request.entry_id,
                action="memory_read",
                success=False,
                details={"reason": "not_found"},
            )
            return None
        self._require_owner_match(scope, actor.agent_id, entry.owner_agent_id)
        self._record_read(hit=True)
        self._record_audit(
            actor=actor,
            scope=scope,
            namespace=request.namespace,
            resource_id=entry.id,
            action="memory_read",
            success=True,
            details={},
        )
        return entry

    def update_entries(
        self, *, actor: MemoryActorContext, requests: Sequence[MemoryUpdateRequest]
    ) -> list[MemoryEntry]:
        self._validate_bulk_size(requests)
        updated: list[MemoryEntry] = []
        for request in requests:
            scope = request.scope or self._default_scope
            target_team_id = self._resolve_target_team_id(
                actor, scope, request.target_team_id
            )
            self._require_permission(
                actor=actor,
                scope=scope,
                action=MemoryAction.WRITE,
                target_team_id=target_team_id,
            )
            store = self._registry.resolve(scope)
            entry = store.get(request.entry_id, scope, request.namespace)
            if entry is None:
                raise ValueError(f"memory entry not found: {request.entry_id}")
            self._require_owner_match(scope, actor.agent_id, entry.owner_agent_id)
            entry.content = request.content or entry.content
            if request.tags is not None:
                entry.tags = list(request.tags)
            if request.priority is not None:
                entry.priority = request.priority
            if request.confidence is not None:
                entry.confidence = request.confidence
            entry.expires_at = request.expires_at
            entry.updated_at = _utc_now()
            updated.append(store.update(entry))
            self._record_write(count=1)
            self._record_audit(
                actor=actor,
                scope=scope,
                namespace=request.namespace,
                resource_id=entry.id,
                action="memory_update",
                success=True,
                details={},
            )
        return updated

    def delete_entries(
        self, *, actor: MemoryActorContext, requests: Sequence[MemoryDeleteRequest]
    ) -> list[bool]:
        self._validate_bulk_size(requests)
        results: list[bool] = []
        for request in requests:
            scope = request.scope or self._default_scope
            target_team_id = self._resolve_target_team_id(
                actor, scope, request.target_team_id
            )
            self._require_permission(
                actor=actor,
                scope=scope,
                action=MemoryAction.WRITE,
                target_team_id=target_team_id,
            )
            store = self._registry.resolve(scope)
            entry = store.get(request.entry_id, scope, request.namespace)
            if entry is not None:
                self._require_owner_match(scope, actor.agent_id, entry.owner_agent_id)
            success = store.delete(request.entry_id, scope, request.namespace)
            results.append(success)
            self._record_write(count=1)
            self._record_audit(
                actor=actor,
                scope=scope,
                namespace=request.namespace,
                resource_id=request.entry_id,
                action="memory_delete",
                success=success,
                details={},
            )
        return results

    def list_entries(
        self,
        *,
        actor: MemoryActorContext,
        scope: MemoryScope | None,
        namespace: str,
        limit: int | None,
        cursor: str | None,
        target_team_id: int | None = None,
    ) -> MemoryListResult:
        resolved_scope = scope or self._default_scope
        target_team = self._resolve_target_team_id(
            actor, resolved_scope, target_team_id
        )
        self._require_permission(
            actor=actor,
            scope=resolved_scope,
            action=MemoryAction.READ,
            target_team_id=target_team,
        )
        page_limit = self._normalize_limit(limit)
        store = self._registry.resolve(resolved_scope)
        owner_agent_id = actor.agent_id if resolved_scope == MemoryScope.AGENT else None
        start = time.perf_counter()
        result = store.list(
            resolved_scope, namespace, page_limit, cursor, owner_agent_id
        )
        self._record_list_latency((time.perf_counter() - start) * 1000)
        self._record_list()
        self._record_audit(
            actor=actor,
            scope=resolved_scope,
            namespace=namespace,
            resource_id="list",
            action="memory_list",
            success=True,
            details={"count": str(len(result.items))},
        )
        return result

    def promote_entry(
        self,
        *,
        actor: MemoryActorContext,
        entry_id: str,
        source_scope: MemoryScope | None,
        target_scope: MemoryScope,
        namespace: str,
        target_team_id: int | None = None,
    ) -> MemoryEntry:
        source = source_scope or self._default_scope
        source_team_id = self._resolve_target_team_id(actor, source, target_team_id)
        self._require_permission(
            actor=actor,
            scope=source,
            action=MemoryAction.READ,
            target_team_id=source_team_id,
        )
        source_store = self._registry.resolve(source)
        entry = source_store.get(entry_id, source, namespace)
        if entry is None:
            raise ValueError(f"memory entry not found: {entry_id}")
        self._require_owner_match(source, actor.agent_id, entry.owner_agent_id)

        target_team = self._resolve_target_team_id(actor, target_scope, target_team_id)
        self._require_permission(
            actor=actor,
            scope=target_scope,
            action=MemoryAction.WRITE,
            target_team_id=target_team,
        )
        target_store = self._registry.resolve(target_scope)
        existing = target_store.get(entry_id, target_scope, namespace)
        if existing and existing.content != entry.content:
            conflict_entry = MemoryEntry(
                id=uuid4().hex,
                scope=target_scope,
                namespace=namespace,
                owner_agent_id=entry.owner_agent_id,
                content=entry.content,
                tags=list(entry.tags) + [f"conflict_with:{existing.id}"],
                priority=entry.priority,
                created_at=_utc_now(),
                updated_at=_utc_now(),
                expires_at=entry.expires_at,
                source=entry.source,
                confidence=entry.confidence,
                is_conflict=True,
            )
            created_conflict = target_store.add(conflict_entry)
            self._record_write(count=1)
            self._record_audit(
                actor=actor,
                scope=target_scope,
                namespace=namespace,
                resource_id=created_conflict.id,
                action="memory_promote_conflict",
                success=True,
                details={"conflict_with": existing.id},
            )
            return created_conflict

        promoted = MemoryEntry(
            id=entry.id,
            scope=target_scope,
            namespace=namespace,
            owner_agent_id=entry.owner_agent_id,
            content=entry.content,
            tags=list(entry.tags),
            priority=entry.priority,
            created_at=_utc_now(),
            updated_at=_utc_now(),
            expires_at=entry.expires_at,
            source=entry.source,
            confidence=entry.confidence,
        )
        created = target_store.add(promoted)
        self._record_write(count=1)
        self._record_audit(
            actor=actor,
            scope=target_scope,
            namespace=namespace,
            resource_id=created.id,
            action="memory_promote",
            success=True,
            details={},
        )
        return created

    def _normalize_limit(self, limit: int | None) -> int:
        page_limit = limit if limit is not None else self._default_page_size
        if page_limit < 1:
            raise ValueError("limit must be at least 1")
        if page_limit > self._max_page_size:
            raise ValueError("limit exceeds maximum page size")
        return page_limit

    def _validate_bulk_size(self, items: Iterable[object]) -> None:
        count = len(list(items))
        if count > self._max_bulk_items:
            raise ValueError(
                f"bulk memory CRUD limit exceeded (max {self._max_bulk_items})"
            )

    def _record_read(self, hit: bool) -> None:
        if self._metrics:
            self._metrics.record_read(hit)

    def _record_write(self, count: int) -> None:
        if self._metrics:
            self._metrics.record_write(count)

    def _record_list(self) -> None:
        if self._metrics:
            self._metrics.record_list()

    def _record_read_latency(self, latency_ms: float) -> None:
        if self._metrics:
            self._metrics.record_read_latency(latency_ms)

    def _record_list_latency(self, latency_ms: float) -> None:
        if self._metrics:
            self._metrics.record_list_latency(latency_ms)

    def _record_audit(
        self,
        *,
        actor: MemoryActorContext,
        scope: MemoryScope,
        namespace: str,
        resource_id: str,
        action: str,
        success: bool,
        details: dict[str, str],
    ) -> None:
        if not self._audit_sink:
            return
        event = MemoryAuditEvent(
            action=action,
            actor_id=actor.agent_id,
            scope=scope,
            namespace=namespace,
            resource_id=resource_id,
            success=success,
            details=details,
        )
        self._audit_sink.record(event)

    def _require_permission(
        self,
        *,
        actor: MemoryActorContext,
        scope: MemoryScope,
        action: MemoryAction,
        target_team_id: int | None,
    ) -> None:
        allowed = check_memory_permission(
            actor_team_id=actor.team_id,
            target_team_id=target_team_id,
            system_type=actor.system_type,
            scope=scope,
            action=action,
        )
        if not allowed:
            raise PermissionError(
                "Memory access denied for "
                f"scope={scope.value} action={action.value} system_type={actor.system_type.value}"
            )

    @staticmethod
    def _require_owner_match(
        scope: MemoryScope, actor_agent_id: str, owner_agent_id: str
    ) -> None:
        if scope == MemoryScope.AGENT and actor_agent_id != owner_agent_id:
            raise PermissionError("Agent scope memory access denied for non-owner.")

    @staticmethod
    def _resolve_target_team_id(
        actor: MemoryActorContext, scope: MemoryScope, target_team_id: int | None
    ) -> int | None:
        if scope == MemoryScope.GLOBAL:
            return None
        return target_team_id or actor.team_id
