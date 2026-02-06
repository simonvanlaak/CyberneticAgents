"""Memory backend configuration."""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from autogen_core.memory import ListMemory

from src.cyberagent.core.paths import resolve_data_path
from src.cyberagent.memory.backends.autogen import AutoGenMemoryStore
from src.cyberagent.memory.backends.hybrid import HybridMemoryStore
from src.cyberagent.memory.backends.vector_index import MemoryVectorIndex
from src.cyberagent.memory.backends.sqlite import SqliteMemoryStore
from src.cyberagent.memory.backends.vector_index import NoopVectorIndex
from src.cyberagent.memory.registry import StaticScopeRegistry

if TYPE_CHECKING:
    from autogen_ext.memory.chromadb._chroma_configs import ChromaDBVectorMemoryConfig


@dataclass(frozen=True)
class MemoryBackendConfig:
    backend: str
    chroma_collection: str
    chroma_persistence_path: str
    chroma_host: str
    chroma_port: int
    chroma_ssl: bool
    sqlite_path: str
    vector_backend: str
    vector_collection: str


def load_memory_backend_config() -> MemoryBackendConfig:
    backend = os.environ.get("MEMORY_BACKEND", "chromadb").lower()
    chroma_collection = os.environ.get("MEMORY_CHROMA_COLLECTION", "memory_store")
    chroma_persistence_path = os.environ.get(
        "MEMORY_CHROMA_PATH", str(resolve_data_path("chroma_db"))
    )
    chroma_host = os.environ.get("MEMORY_CHROMA_HOST", "")
    chroma_port_raw = os.environ.get("MEMORY_CHROMA_PORT", "8000")
    try:
        chroma_port = int(chroma_port_raw)
    except ValueError:
        chroma_port = 8000
    chroma_ssl_raw = os.environ.get("MEMORY_CHROMA_SSL", "false")
    chroma_ssl = str(chroma_ssl_raw).lower() in {"1", "true", "yes"}
    return MemoryBackendConfig(
        backend=backend,
        chroma_collection=chroma_collection,
        chroma_persistence_path=chroma_persistence_path,
        chroma_host=chroma_host,
        chroma_port=chroma_port,
        chroma_ssl=chroma_ssl,
        sqlite_path=os.environ.get(
            "MEMORY_SQLITE_PATH", str(resolve_data_path("memory.db"))
        ),
        vector_backend=os.environ.get("MEMORY_VECTOR_BACKEND", "none").lower(),
        vector_collection=os.environ.get("MEMORY_VECTOR_COLLECTION", "memory_vectors"),
    )


def build_memory_registry(config: MemoryBackendConfig) -> StaticScopeRegistry:
    if config.backend == "list":
        return StaticScopeRegistry(
            agent_store=AutoGenMemoryStore(ListMemory(name="agent_memory")),
            team_store=AutoGenMemoryStore(ListMemory(name="team_memory")),
            global_store=AutoGenMemoryStore(ListMemory(name="global_memory")),
        )

    if config.backend == "chromadb":
        sqlite_store = SqliteMemoryStore(Path(config.sqlite_path))
        vector_index = _build_vector_index(config)
        return StaticScopeRegistry(
            agent_store=HybridMemoryStore(sqlite_store, vector_index),
            team_store=HybridMemoryStore(sqlite_store, vector_index),
            global_store=HybridMemoryStore(sqlite_store, vector_index),
        )

    raise ValueError(f"Unsupported memory backend '{config.backend}'.")


def _build_vector_index(config: MemoryBackendConfig) -> MemoryVectorIndex:
    if config.vector_backend != "chromadb":
        return NoopVectorIndex()
    try:
        from src.cyberagent.memory.backends.chromadb_vector import ChromaDBVectorIndex
    except ImportError:
        return NoopVectorIndex()
    try:
        vector_config = _build_chroma_vector_config(config)
    except ImportError:
        return NoopVectorIndex()
    try:
        return ChromaDBVectorIndex(config=vector_config)
    except ImportError:
        return NoopVectorIndex()


def _build_chroma_config(
    config: MemoryBackendConfig, *, suffix: str
) -> "ChromaDBVectorMemoryConfig":
    try:
        from autogen_ext.memory.chromadb._chroma_configs import (
            HttpChromaDBVectorMemoryConfig,
            PersistentChromaDBVectorMemoryConfig,
        )
    except ImportError as exc:
        raise ImportError(
            "ChromaDB configuration requires the chromadb extra. "
            "Install with `pip install autogen-ext[chromadb]`."
        ) from exc

    collection_name = f"{config.chroma_collection}_{suffix}"
    if config.chroma_host:
        return cast(
            "ChromaDBVectorMemoryConfig",
            HttpChromaDBVectorMemoryConfig(
                collection_name=collection_name,
                host=config.chroma_host,
                port=config.chroma_port,
                ssl=config.chroma_ssl,
            ),
        )
    return cast(
        "ChromaDBVectorMemoryConfig",
        PersistentChromaDBVectorMemoryConfig(
            collection_name=collection_name,
            persistence_path=config.chroma_persistence_path,
        ),
    )


def _build_chroma_vector_config(
    config: MemoryBackendConfig,
) -> "ChromaDBVectorMemoryConfig":
    try:
        from autogen_ext.memory.chromadb._chroma_configs import (
            HttpChromaDBVectorMemoryConfig,
            PersistentChromaDBVectorMemoryConfig,
        )
    except ImportError as exc:
        raise ImportError(
            "ChromaDB configuration requires the chromadb extra. "
            "Install with `pip install autogen-ext[chromadb]`."
        ) from exc

    if config.chroma_host:
        return cast(
            "ChromaDBVectorMemoryConfig",
            HttpChromaDBVectorMemoryConfig(
                collection_name=config.vector_collection,
                host=config.chroma_host,
                port=config.chroma_port,
                ssl=config.chroma_ssl,
            ),
        )
    return cast(
        "ChromaDBVectorMemoryConfig",
        PersistentChromaDBVectorMemoryConfig(
            collection_name=config.vector_collection,
            persistence_path=config.chroma_persistence_path,
        ),
    )
