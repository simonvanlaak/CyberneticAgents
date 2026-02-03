"""Memory backend adapters."""

from typing import Any

from src.cyberagent.memory.backends.autogen import AutoGenMemoryStore

__all__ = ["AutoGenMemoryStore", "ChromaDBMemoryFactory"]


def __getattr__(name: str) -> Any:
    if name == "ChromaDBMemoryFactory":
        from src.cyberagent.memory.backends.chromadb import ChromaDBMemoryFactory

        return ChromaDBMemoryFactory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
