from src.cyberagent.memory.backends.sqlite import SqliteMemoryStore
from src.cyberagent.memory.crud import MemoryActorContext
from src.cyberagent.memory.memengine import MemEngine
from src.cyberagent.memory.models import MemoryLayer, MemoryScope, MemorySource
from src.cyberagent.memory.reflection import MemoryReflectionService
from src.cyberagent.memory.registry import StaticScopeRegistry
from src.cyberagent.memory.session import MemorySessionConfig, MemorySessionRecorder
from src.enums import SystemType


def _actor() -> MemoryActorContext:
    return MemoryActorContext(
        agent_id="root_sys1",
        system_id=1,
        team_id=1,
        system_type=SystemType.OPERATION,
    )


def test_session_recorder_writes_session_entry(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    registry = StaticScopeRegistry(store, store, store)
    engine = MemEngine(registry=registry)
    reflection = MemoryReflectionService(registry=registry, engine=engine)
    recorder = MemorySessionRecorder(
        registry=registry,
        reflection_service=reflection,
        config=MemorySessionConfig(
            max_log_chars=200,
            compaction_threshold_chars=1000,
            reflection_interval_seconds=9999,
        ),
    )
    recorder.record(
        actor=_actor(),
        scope=MemoryScope.AGENT,
        namespace="root_sys1",
        logs=["user: hello", "assistant: hi there"],
    )
    result = store.list(
        MemoryScope.AGENT,
        "root_sys1",
        limit=10,
        cursor=None,
        owner_agent_id="root_sys1",
    )
    assert result.items
    entry = result.items[0]
    assert entry.layer == MemoryLayer.SESSION
    assert entry.source == MemorySource.TOOL


def test_session_recorder_compacts_on_threshold(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    registry = StaticScopeRegistry(store, store, store)
    engine = MemEngine(registry=registry)
    reflection = MemoryReflectionService(registry=registry, engine=engine)
    recorder = MemorySessionRecorder(
        registry=registry,
        reflection_service=reflection,
        config=MemorySessionConfig(
            max_log_chars=200,
            compaction_threshold_chars=40,
            reflection_interval_seconds=9999,
        ),
    )
    recorder.record(
        actor=_actor(),
        scope=MemoryScope.AGENT,
        namespace="root_sys1",
        logs=["user: " + ("hello " * 10)],
    )
    result = store.list(
        MemoryScope.AGENT,
        "root_sys1",
        limit=10,
        cursor=None,
        owner_agent_id="root_sys1",
    )
    assert any(entry.layer == MemoryLayer.LONG_TERM for entry in result.items)


def test_session_recorder_prunes_excess_entries(tmp_path) -> None:
    store = SqliteMemoryStore(tmp_path / "memory.db")
    registry = StaticScopeRegistry(store, store, store)
    engine = MemEngine(registry=registry)
    reflection = MemoryReflectionService(registry=registry, engine=engine)
    recorder = MemorySessionRecorder(
        registry=registry,
        reflection_service=reflection,
        config=MemorySessionConfig(
            max_log_chars=200,
            compaction_threshold_chars=1000,
            reflection_interval_seconds=9999,
            max_entries_per_namespace=1,
        ),
    )
    recorder.record(
        actor=_actor(),
        scope=MemoryScope.AGENT,
        namespace="root_sys1",
        logs=["user: one"],
    )
    recorder.record(
        actor=_actor(),
        scope=MemoryScope.AGENT,
        namespace="root_sys1",
        logs=["user: two"],
    )
    result = store.list(
        MemoryScope.AGENT,
        "root_sys1",
        limit=10,
        cursor=None,
        owner_agent_id="root_sys1",
    )
    assert len(result.items) == 1
