import sys
from types import ModuleType

import pytest

from src.agents import system_base as system_base_module
from src.agents.system_base import SystemBase
from src.cyberagent.memory.config import (
    build_memory_registry,
    load_memory_backend_config,
)
from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.enums import SystemType
from datetime import datetime, timezone


class DummyAssistantAgent:
    def __init__(self, *args, **kwargs) -> None:
        self._tools = kwargs.get("tools", [])


class DummySystem(SystemBase):
    def __init__(self) -> None:
        super().__init__(
            "System4/root",
            identity_prompt="test",
            responsibility_prompts=["test"],
        )


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


def _configure_system(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("CYBERAGENT_ACTIVE_TEAM_ID", "1")
    monkeypatch.setenv("MEMORY_BACKEND", "chromadb")
    monkeypatch.setenv("MEMORY_SQLITE_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("MEMORY_VECTOR_BACKEND", "chromadb")
    monkeypatch.setenv("MEMORY_VECTOR_COLLECTION", "memory_vectors")
    _install_fake_chromadb()
    monkeypatch.setattr(
        system_base_module.team_service, "get_team", lambda team_id: object()
    )
    monkeypatch.setattr(
        system_base_module.system_service,
        "ensure_default_systems_for_team",
        lambda team_id: [],
    )
    monkeypatch.setattr(system_base_module, "mark_team_active", lambda team_id: None)
    monkeypatch.setattr(
        system_base_module, "get_agent_skill_tools", lambda agent_id: []
    )
    monkeypatch.setattr(system_base_module, "AssistantAgent", DummyAssistantAgent)
    monkeypatch.setattr(
        system_base_module,
        "get_system_from_agent_id",
        lambda agent_id: type(
            "S",
            (),
            {
                "id": 1,
                "agent_id_str": "root_sys4",
                "team_id": 1,
                "type": SystemType.INTELLIGENCE,
            },
        )(),
    )


def _seed_memory() -> None:
    registry = build_memory_registry(load_memory_backend_config())
    store = registry.resolve(MemoryScope.AGENT)
    now = datetime.now(timezone.utc)
    store.add(
        MemoryEntry(
            id="mem-1",
            scope=MemoryScope.AGENT,
            namespace="root_sys4",
            owner_agent_id="root_sys4",
            content="unrelated content",
            tags=["alpha"],
            priority=MemoryPriority.MEDIUM,
            created_at=now,
            updated_at=now,
            expires_at=None,
            source=MemorySource.MANUAL,
            confidence=0.8,
            layer=MemoryLayer.SESSION,
        )
    )


def test_build_memory_context_includes_memory_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _configure_system(monkeypatch, tmp_path)
    _seed_memory()
    system = DummySystem()
    fake_message = type("Msg", (), {"to_text": lambda self: "unrelated"})()
    context = system._build_memory_context(fake_message)  # type: ignore[arg-type]
    assert any("mem-1" in entry for entry in context)
