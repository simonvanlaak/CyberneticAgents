"""Memory backend configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from autogen_core.memory import ListMemory

from src.cyberagent.memory.backends.autogen import AutoGenMemoryStore
from src.cyberagent.memory.backends.chromadb import ChromaDBMemoryFactory
from src.cyberagent.memory.models import MemoryScope
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


def load_memory_backend_config() -> MemoryBackendConfig:
    backend = os.environ.get("MEMORY_BACKEND", "list").lower()
    chroma_collection = os.environ.get("MEMORY_CHROMA_COLLECTION", "memory_store")
    chroma_persistence_path = os.environ.get("MEMORY_CHROMA_PATH", "data/chroma_db")
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
    )


def build_memory_registry(config: MemoryBackendConfig) -> StaticScopeRegistry:
    if config.backend == "list":
        return StaticScopeRegistry(
            agent_store=AutoGenMemoryStore(ListMemory(name="agent_memory")),
            team_store=AutoGenMemoryStore(ListMemory(name="team_memory")),
            global_store=AutoGenMemoryStore(ListMemory(name="global_memory")),
        )

    if config.backend == "chromadb":
        factory = ChromaDBMemoryFactory()
        agent_store = factory.create_store(
            config=_build_chroma_config(config, suffix=MemoryScope.AGENT.value)
        )
        team_store = factory.create_store(
            config=_build_chroma_config(config, suffix=MemoryScope.TEAM.value)
        )
        global_store = factory.create_store(
            config=_build_chroma_config(config, suffix=MemoryScope.GLOBAL.value)
        )
        return StaticScopeRegistry(
            agent_store=agent_store,
            team_store=team_store,
            global_store=global_store,
        )

    raise ValueError(f"Unsupported memory backend '{config.backend}'.")


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
