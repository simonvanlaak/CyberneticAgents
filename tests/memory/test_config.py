from src.cyberagent.memory.config import (
    MemoryBackendConfig,
    build_memory_registry,
    load_memory_backend_config,
)
from src.cyberagent.memory.models import MemoryScope


def test_load_memory_backend_config_defaults(monkeypatch) -> None:
    monkeypatch.delenv("MEMORY_BACKEND", raising=False)
    monkeypatch.delenv("MEMORY_CHROMA_COLLECTION", raising=False)
    monkeypatch.delenv("MEMORY_CHROMA_PATH", raising=False)
    monkeypatch.delenv("MEMORY_CHROMA_HOST", raising=False)
    monkeypatch.delenv("MEMORY_CHROMA_PORT", raising=False)
    monkeypatch.delenv("MEMORY_CHROMA_SSL", raising=False)

    config = load_memory_backend_config()
    assert config.backend == "list"
    assert config.chroma_collection == "memory_store"
    assert config.chroma_persistence_path == "data/chroma_db"
    assert config.chroma_host == ""
    assert config.chroma_port == 8000
    assert config.chroma_ssl is False


def test_build_memory_registry_list_backend() -> None:
    config = MemoryBackendConfig(
        backend="list",
        chroma_collection="memory_store",
        chroma_persistence_path="data/chroma_db",
        chroma_host="",
        chroma_port=8000,
        chroma_ssl=False,
    )
    registry = build_memory_registry(config)
    assert registry.resolve(MemoryScope.AGENT) is not None
    assert registry.resolve(MemoryScope.TEAM) is not None
    assert registry.resolve(MemoryScope.GLOBAL) is not None
