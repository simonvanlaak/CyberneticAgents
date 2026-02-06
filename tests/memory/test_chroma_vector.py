import sys
from types import ModuleType

from src.cyberagent.core.paths import resolve_data_path
from src.cyberagent.memory.backends.chroma_index import ChromaVectorIndex
from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from datetime import datetime, timezone


class FakeCollection:
    def __init__(self) -> None:
        self.upserts = []
        self.deleted = []

    def upsert(self, ids, documents, metadatas):  # type: ignore[no-untyped-def]
        self.upserts.append((ids, documents, metadatas))

    def query(self, query_texts, n_results):  # type: ignore[no-untyped-def]
        ids = [self.upserts[0][0][0]] if self.upserts else []
        return {"ids": [ids]}

    def delete(self, ids):  # type: ignore[no-untyped-def]
        self.deleted.extend(ids)


class FakeClient:
    def __init__(self) -> None:
        self.collection = FakeCollection()

    def get_or_create_collection(self, name):  # type: ignore[no-untyped-def]
        return self.collection


def _install_fake_chromadb() -> None:
    module = ModuleType("chromadb")
    setattr(module, "PersistentClient", lambda path: FakeClient())
    setattr(module, "HttpClient", lambda host, port, ssl: FakeClient())
    sys.modules["chromadb"] = module


def _entry(entry_id: str) -> MemoryEntry:
    now = datetime.now(timezone.utc)
    return MemoryEntry(
        id=entry_id,
        scope=MemoryScope.AGENT,
        namespace="root",
        owner_agent_id="root_sys1",
        content="hello",
        tags=["alpha"],
        priority=MemoryPriority.MEDIUM,
        created_at=now,
        updated_at=now,
        expires_at=None,
        source=MemorySource.MANUAL,
        confidence=0.8,
        layer=MemoryLayer.SESSION,
    )


def test_chroma_vector_index_roundtrip() -> None:
    _install_fake_chromadb()
    index = ChromaVectorIndex(
        collection="memory_vectors",
        persistence_path=str(resolve_data_path("chroma_db")),
        host="",
        port=8000,
        ssl=False,
    )
    entry = _entry("mem-1")
    index.upsert(entry)
    ids = index.query("hello", limit=3)
    assert ids == ["mem-1"]
    index.delete("mem-1")
