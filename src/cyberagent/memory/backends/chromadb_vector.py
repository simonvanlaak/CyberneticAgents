"""ChromaDB vector index using AutoGen ChromaDBVectorMemory."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from autogen_core.memory import MemoryContent, MemoryMimeType

from src.cyberagent.memory.backends.chromadb import ChromaDBMemoryFactory
from src.cyberagent.memory.backends.vector_index import MemoryVectorIndex
from src.cyberagent.memory.models import MemoryEntry


@dataclass(slots=True)
class ChromaDBVectorIndex(MemoryVectorIndex):
    """Vector index adapter that uses ChromaDBVectorMemory."""

    config: Any

    def __post_init__(self) -> None:
        factory = ChromaDBMemoryFactory()
        self._memory = factory.create_memory(config=self.config)

    def upsert(self, entry: MemoryEntry) -> None:
        content = MemoryContent(
            content=entry.content,
            mime_type=MemoryMimeType.TEXT,
            metadata={
                "id": entry.id,
                "scope": entry.scope.value,
                "namespace": entry.namespace,
                "owner_agent_id": entry.owner_agent_id,
                "tags": list(entry.tags),
                "layer": entry.layer.value,
            },
        )
        _run_async(self._memory.add(content))

    def delete(self, entry_id: str) -> None:
        # AutoGen Memory protocol does not support deletes; rely on record store filter.
        return None

    def query(self, text: str, limit: int) -> list[str]:
        result = _run_async(self._memory.query(text))
        ids: list[str] = []
        for content in result.results:
            if content.metadata and "id" in content.metadata:
                ids.append(str(content.metadata["id"]))
            if len(ids) >= limit:
                break
        return ids


def _run_async(coro):  # type: ignore[no-untyped-def]
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("ChromaDBVectorIndex cannot run inside an active event loop.")
