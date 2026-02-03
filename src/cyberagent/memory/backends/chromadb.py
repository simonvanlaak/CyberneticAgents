"""ChromaDB-backed AutoGen memory helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from autogen_core.memory import Memory

from src.cyberagent.memory.backends.autogen import AutoGenMemoryStore
from src.cyberagent.memory.store import MemoryStore

if TYPE_CHECKING:
    from autogen_ext.memory.chromadb._chroma_configs import ChromaDBVectorMemoryConfig


@dataclass(slots=True)
class ChromaDBMemoryFactory:
    """Factory for ChromaDB-based AutoGen memories."""

    def create_memory(
        self, *, config: "ChromaDBVectorMemoryConfig | None" = None
    ) -> Memory:
        try:
            from autogen_ext.memory.chromadb import ChromaDBVectorMemory
        except ImportError as exc:
            raise ImportError(
                "ChromaDBVectorMemory requires the chromadb extra. "
                "Install with `pip install autogen-ext[chromadb]`."
            ) from exc
        return ChromaDBVectorMemory(config=config)

    def create_store(
        self, *, config: "ChromaDBVectorMemoryConfig | None" = None
    ) -> MemoryStore:
        memory = self.create_memory(config=config)
        return AutoGenMemoryStore(memory)
