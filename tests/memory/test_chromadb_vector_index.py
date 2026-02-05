from __future__ import annotations

import sys
from types import ModuleType
from typing import Any, cast

from autogen_core.memory import MemoryContent, MemoryMimeType

from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)

from datetime import datetime, timezone


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


def _entry(entry_id: str) -> MemoryEntry:
    now = datetime.now(timezone.utc)
    return MemoryEntry(
        id=entry_id,
        scope=MemoryScope.AGENT,
        namespace="root",
        owner_agent_id="root_sys1",
        content="hello world",
        tags=["alpha"],
        priority=MemoryPriority.MEDIUM,
        created_at=now,
        updated_at=now,
        expires_at=None,
        source=MemorySource.MANUAL,
        confidence=0.9,
        layer=MemoryLayer.SESSION,
    )


def test_chromadb_vector_index_roundtrip() -> None:
    _install_fake_autogen_chromadb()
    from src.cyberagent.memory.backends.chromadb_vector import ChromaDBVectorIndex

    index = ChromaDBVectorIndex(config=object())
    entry = _entry("mem-1")
    index.upsert(entry)
    ids = index.query("hello", limit=5)
    assert ids == ["mem-1"]
    index.delete("mem-1")

    content = MemoryContent(
        content="direct",
        mime_type=MemoryMimeType.TEXT,
        metadata={"id": "mem-2"},
    )
    index.upsert(entry)
    memory = cast(Any, getattr(index, "_memory"))
    memory._items.append(content)  # type: ignore[attr-defined]
    ids = index.query("direct", limit=5)
    assert "mem-2" in ids
