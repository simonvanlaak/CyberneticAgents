import pytest

from src.cyberagent.memory.backends.chromadb import ChromaDBMemoryFactory


def test_chromadb_factory_requires_dependency() -> None:
    factory = ChromaDBMemoryFactory()
    with pytest.raises(ImportError):
        factory.create_memory()
