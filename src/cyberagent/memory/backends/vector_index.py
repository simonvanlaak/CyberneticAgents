"""Vector index interfaces for memory retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.cyberagent.memory.models import MemoryEntry


class MemoryVectorIndex(Protocol):
    def upsert(self, entry: MemoryEntry) -> None:
        """Add or update an entry in the vector index."""
        ...

    def delete(self, entry_id: str) -> None:
        """Remove an entry from the vector index."""
        ...

    def query(self, text: str, limit: int) -> list[str]:
        """Return memory entry IDs for a semantic query."""
        ...


@dataclass(slots=True)
class NoopVectorIndex:
    """Vector index placeholder when no semantic backend is available."""

    def upsert(self, entry: MemoryEntry) -> None:
        return None

    def delete(self, entry_id: str) -> None:
        return None

    def query(self, text: str, limit: int) -> list[str]:
        return []
