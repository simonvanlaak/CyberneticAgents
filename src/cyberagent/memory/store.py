"""Memory store interfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryListResult,
    MemoryQuery,
    MemoryScope,
)


@runtime_checkable
class MemoryStore(Protocol):
    """Interface for memory storage backends."""

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        """Create a new memory entry."""
        ...

    def get(
        self, entry_id: str, scope: MemoryScope, namespace: str
    ) -> MemoryEntry | None:
        """Fetch a memory entry by id."""
        ...

    def update(self, entry: MemoryEntry) -> MemoryEntry:
        """Update an existing memory entry."""
        ...

    def delete(self, entry_id: str, scope: MemoryScope, namespace: str) -> bool:
        """Delete a memory entry."""
        ...

    def query(self, query: MemoryQuery) -> MemoryListResult:
        """Query memory entries."""
        ...

    def list(
        self,
        scope: MemoryScope,
        namespace: str,
        limit: int,
        cursor: str | None,
        owner_agent_id: str | None = None,
    ) -> MemoryListResult:
        """List memory entries for a scope."""
        ...
