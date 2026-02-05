"""ChromaDB vector index wrapper."""

from __future__ import annotations

from dataclasses import dataclass

from src.cyberagent.memory.backends.vector_index import MemoryVectorIndex
from src.cyberagent.memory.models import MemoryEntry


@dataclass(slots=True)
class ChromaVectorIndex(MemoryVectorIndex):
    collection: str
    persistence_path: str
    host: str
    port: int
    ssl: bool

    def __post_init__(self) -> None:
        try:
            import chromadb  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "ChromaVectorIndex requires chromadb. "
                "Install with `pip install chromadb`."
            ) from exc
        if self.host:
            client_factory = getattr(chromadb, "HttpClient", None)
            if client_factory is None:
                raise ImportError("chromadb HttpClient is unavailable.")
            client = client_factory(host=self.host, port=self.port, ssl=self.ssl)
        else:
            client_factory = getattr(chromadb, "PersistentClient", None)
            if client_factory is None:
                raise ImportError("chromadb PersistentClient is unavailable.")
            client = client_factory(path=self.persistence_path)
        self._collection = client.get_or_create_collection(self.collection)

    def delete(self, entry_id: str) -> None:
        self._collection.delete(ids=[entry_id])

    def upsert(self, entry: MemoryEntry) -> None:
        metadata = {
            "scope": entry.scope.value,
            "namespace": entry.namespace,
            "owner_agent_id": entry.owner_agent_id,
            "tags": list(entry.tags),
            "priority": entry.priority.value,
            "source": entry.source.value,
            "layer": entry.layer.value,
        }
        self._collection.upsert(
            ids=[entry.id],
            documents=[entry.content],
            metadatas=[metadata],
        )

    def query(self, text: str, limit: int) -> list[str]:
        result = self._collection.query(query_texts=[text], n_results=limit)
        ids = result.get("ids", [[]])
        if not ids:
            return []
        return [str(entry_id) for entry_id in ids[0]]
