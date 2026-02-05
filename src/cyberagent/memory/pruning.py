"""Memory pruning helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.cyberagent.memory.crud import MemoryActorContext
from src.cyberagent.memory.models import MemoryEntry, MemoryPriority, MemoryScope
from src.cyberagent.memory.permissions import MemoryAction, check_memory_permission
from src.cyberagent.memory.registry import StaticScopeRegistry


@dataclass(frozen=True)
class MemoryPruningConfig:
    max_entries_per_namespace: int = 1000


class MemoryPruner:
    def __init__(
        self,
        *,
        registry: StaticScopeRegistry,
        config: MemoryPruningConfig | None = None,
    ) -> None:
        self._registry = registry
        self._config = config or MemoryPruningConfig()

    def prune(
        self,
        *,
        actor: MemoryActorContext,
        scope: MemoryScope,
        namespace: str,
    ) -> list[str]:
        self._require_permission(actor=actor, scope=scope)
        store = self._registry.resolve(scope)
        owner_agent_id = actor.agent_id if scope == MemoryScope.AGENT else None
        entries = _collect_entries(store, scope, namespace, owner_agent_id)
        deleted: list[str] = []

        now = datetime.now(timezone.utc)
        for entry in list(entries):
            if entry.expires_at and entry.expires_at <= now:
                if store.delete(entry.id, scope, namespace):
                    deleted.append(entry.id)
                    entries.remove(entry)

        if len(entries) > self._config.max_entries_per_namespace:
            entries_sorted = sorted(
                entries,
                key=lambda entry: (
                    _priority_rank(entry.priority),
                    entry.created_at,
                ),
            )
            excess = len(entries_sorted) - self._config.max_entries_per_namespace
            for entry in entries_sorted[:excess]:
                if store.delete(entry.id, scope, namespace):
                    deleted.append(entry.id)
        return deleted

    @staticmethod
    def _require_permission(*, actor: MemoryActorContext, scope: MemoryScope) -> None:
        allowed = check_memory_permission(
            actor_team_id=actor.team_id,
            target_team_id=actor.team_id,
            system_type=actor.system_type,
            scope=scope,
            action=MemoryAction.WRITE,
        )
        if not allowed:
            raise PermissionError(
                "Memory prune denied for "
                f"scope={scope.value} system_type={actor.system_type.value}"
            )


def _collect_entries(
    store,
    scope: MemoryScope,
    namespace: str,
    owner_agent_id: str | None,
) -> list[MemoryEntry]:
    entries: list[MemoryEntry] = []
    cursor = None
    while True:
        result = store.list(
            scope, namespace, limit=100, cursor=cursor, owner_agent_id=owner_agent_id
        )
        entries.extend(result.items)
        if not result.has_more:
            break
        cursor = result.next_cursor
    return entries


def _priority_rank(priority: MemoryPriority) -> int:
    order = {
        MemoryPriority.LOW: 0,
        MemoryPriority.MEDIUM: 1,
        MemoryPriority.HIGH: 2,
    }
    return order.get(priority, 0)
