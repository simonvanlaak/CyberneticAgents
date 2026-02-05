import sys
from types import ModuleType

from src.cyberagent.memory.config import (
    build_memory_registry,
    load_memory_backend_config,
)
from src.cyberagent.memory.crud import MemoryActorContext
from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.memory.retrieval import MemoryRetrievalService
from src.enums import SystemType
from datetime import datetime, timezone


class FakeCollection:
    def __init__(self) -> None:
        self.upserts = []

    def upsert(self, ids, documents, metadatas):  # type: ignore[no-untyped-def]
        self.upserts.append((ids, documents, metadatas))

    def query(self, query_texts, n_results):  # type: ignore[no-untyped-def]
        ids = [self.upserts[0][0][0]] if self.upserts else []
        return {"ids": [ids]}

    def delete(self, ids):  # type: ignore[no-untyped-def]
        return None


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


def _install_fake_autogen_chromadb() -> None:
    class FakeQueryResult:
        def __init__(self, results):  # type: ignore[no-untyped-def]
            self.results = results

    class FakeChromaDBVectorMemory:
        def __init__(self, config=None):  # type: ignore[no-untyped-def]
            self.config = config
            self._items = []

        async def add(self, content):  # type: ignore[no-untyped-def]
            self._items.append(content)

        async def query(self, text):  # type: ignore[no-untyped-def]
            return FakeQueryResult(list(self._items))

    class FakeConfig:
        def __init__(self, collection_name, **kwargs):  # type: ignore[no-untyped-def]
            self.collection_name = collection_name
            self.params = kwargs

    chroma_module = ModuleType("autogen_ext.memory.chromadb")
    setattr(chroma_module, "ChromaDBVectorMemory", FakeChromaDBVectorMemory)
    configs_module = ModuleType("autogen_ext.memory.chromadb._chroma_configs")
    setattr(configs_module, "PersistentChromaDBVectorMemoryConfig", FakeConfig)
    setattr(configs_module, "HttpChromaDBVectorMemoryConfig", FakeConfig)
    sys.modules["autogen_ext.memory.chromadb"] = chroma_module
    sys.modules["autogen_ext.memory.chromadb._chroma_configs"] = configs_module


def _entry(entry_id: str, content: str) -> MemoryEntry:
    now = datetime.now(timezone.utc)
    return MemoryEntry(
        id=entry_id,
        scope=MemoryScope.AGENT,
        namespace="root",
        owner_agent_id="root_sys1",
        content=content,
        tags=["alpha"],
        priority=MemoryPriority.MEDIUM,
        created_at=now,
        updated_at=now,
        expires_at=None,
        source=MemorySource.MANUAL,
        confidence=0.9,
        layer=MemoryLayer.SESSION,
    )


def test_vector_backend_enables_semantic_recall(monkeypatch, tmp_path) -> None:
    _install_fake_chromadb()
    _install_fake_autogen_chromadb()
    monkeypatch.setenv("MEMORY_BACKEND", "chromadb")
    monkeypatch.setenv("MEMORY_SQLITE_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("MEMORY_VECTOR_BACKEND", "chromadb")
    monkeypatch.setenv("MEMORY_VECTOR_COLLECTION", "memory_vectors")

    registry = build_memory_registry(load_memory_backend_config())
    store = registry.resolve(MemoryScope.AGENT)
    store.add(_entry("mem-1", "unrelated content"))

    actor = MemoryActorContext(
        agent_id="root_sys1",
        system_id=1,
        team_id=1,
        system_type=SystemType.OPERATION,
    )
    service = MemoryRetrievalService(registry=registry)
    result = service.search_entries(
        actor=actor,
        scope=MemoryScope.AGENT,
        namespace="root",
        query_text="semantic",
        limit=5,
    )
    assert result.items
    assert result.items[0].id == "mem-1"
