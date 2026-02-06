import sys
from types import ModuleType
from typing import Any, cast

from src.cyberagent.memory.config import (
    MemoryBackendConfig,
    build_memory_registry,
    load_memory_backend_config,
    _build_vector_index,
)
from src.cyberagent.memory.models import MemoryScope
from src.cyberagent.core.paths import resolve_data_path


def test_load_memory_backend_config_defaults(monkeypatch) -> None:
    monkeypatch.delenv("MEMORY_BACKEND", raising=False)
    monkeypatch.delenv("MEMORY_CHROMA_COLLECTION", raising=False)
    monkeypatch.delenv("MEMORY_CHROMA_PATH", raising=False)
    monkeypatch.delenv("MEMORY_CHROMA_HOST", raising=False)
    monkeypatch.delenv("MEMORY_CHROMA_PORT", raising=False)
    monkeypatch.delenv("MEMORY_CHROMA_SSL", raising=False)
    monkeypatch.delenv("MEMORY_SQLITE_PATH", raising=False)
    monkeypatch.delenv("MEMORY_VECTOR_BACKEND", raising=False)
    monkeypatch.delenv("MEMORY_VECTOR_COLLECTION", raising=False)

    config = load_memory_backend_config()
    assert config.backend == "chromadb"
    assert config.chroma_collection == "memory_store"
    assert config.chroma_persistence_path == str(resolve_data_path("chroma_db"))
    assert config.chroma_host == ""
    assert config.chroma_port == 8000
    assert config.chroma_ssl is False
    assert config.sqlite_path == str(resolve_data_path("memory.db"))
    assert config.vector_backend == "none"
    assert config.vector_collection == "memory_vectors"


def test_build_memory_registry_list_backend() -> None:
    config = MemoryBackendConfig(
        backend="list",
        chroma_collection="memory_store",
        chroma_persistence_path=str(resolve_data_path("chroma_db")),
        chroma_host="",
        chroma_port=8000,
        chroma_ssl=False,
        sqlite_path=str(resolve_data_path("memory.db")),
        vector_backend="none",
        vector_collection="memory_vectors",
    )
    registry = build_memory_registry(config)
    assert registry.resolve(MemoryScope.AGENT) is not None
    assert registry.resolve(MemoryScope.TEAM) is not None
    assert registry.resolve(MemoryScope.GLOBAL) is not None


def test_build_vector_index_prefers_chromadb_vector_backend() -> None:
    class FakeConfig:
        def __init__(self, collection_name, **kwargs):  # type: ignore[no-untyped-def]
            self.collection_name = collection_name
            self.params = kwargs

    class FakeChromaDBVectorMemory:
        def __init__(self, config=None):  # type: ignore[no-untyped-def]
            self.config = config

        async def add(self, _content):  # type: ignore[no-untyped-def]
            return None

        async def query(self, _text):  # type: ignore[no-untyped-def]
            class Result:
                results = []

            return Result()

    chroma_module = ModuleType("autogen_ext.memory.chromadb")
    setattr(chroma_module, "ChromaDBVectorMemory", FakeChromaDBVectorMemory)
    configs_module = ModuleType("autogen_ext.memory.chromadb._chroma_configs")
    setattr(configs_module, "PersistentChromaDBVectorMemoryConfig", FakeConfig)
    setattr(configs_module, "HttpChromaDBVectorMemoryConfig", FakeConfig)
    sys.modules["autogen_ext.memory.chromadb"] = chroma_module
    sys.modules["autogen_ext.memory.chromadb._chroma_configs"] = configs_module

    config = MemoryBackendConfig(
        backend="chromadb",
        chroma_collection="memory_store",
        chroma_persistence_path=str(resolve_data_path("chroma_db")),
        chroma_host="",
        chroma_port=8000,
        chroma_ssl=False,
        sqlite_path=str(resolve_data_path("memory.db")),
        vector_backend="chromadb",
        vector_collection="memory_vectors",
    )
    index = _build_vector_index(config)
    assert index.__class__.__name__ == "ChromaDBVectorIndex"
    memory = cast(Any, getattr(index, "_memory"))
    assert memory.config.collection_name == "memory_vectors"
