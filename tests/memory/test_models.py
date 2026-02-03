import datetime

import pytest

from src.cyberagent.memory.models import (
    MemoryAuditEvent,
    MemoryEntry,
    MemoryListResult,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)


def test_memory_scope_values() -> None:
    assert MemoryScope.AGENT.value == "agent"
    assert MemoryScope.TEAM.value == "team"
    assert MemoryScope.GLOBAL.value == "global"


def test_memory_entry_validates_confidence_range() -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    with pytest.raises(ValueError):
        MemoryEntry(
            id="mem-1",
            scope=MemoryScope.AGENT,
            namespace="root",
            owner_agent_id="root_sys1",
            content="bad confidence",
            priority=MemoryPriority.MEDIUM,
            created_at=now,
            updated_at=now,
            source=MemorySource.MANUAL,
            confidence=-0.1,
        )
    with pytest.raises(ValueError):
        MemoryEntry(
            id="mem-2",
            scope=MemoryScope.AGENT,
            namespace="root",
            owner_agent_id="root_sys1",
            content="bad confidence",
            priority=MemoryPriority.MEDIUM,
            created_at=now,
            updated_at=now,
            source=MemorySource.MANUAL,
            confidence=1.1,
        )


def test_memory_entry_defaults_tags_and_updated_at() -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    entry = MemoryEntry(
        id="mem-3",
        scope=MemoryScope.AGENT,
        namespace="root",
        owner_agent_id="root_sys1",
        content="ok",
        priority=MemoryPriority.MEDIUM,
        created_at=now,
        updated_at=None,
        source=MemorySource.MANUAL,
        confidence=0.5,
    )
    assert entry.tags == []
    assert entry.updated_at == now


def test_memory_list_result_requires_cursor_when_has_more() -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    entry = MemoryEntry(
        id="mem-4",
        scope=MemoryScope.AGENT,
        namespace="root",
        owner_agent_id="root_sys1",
        content="ok",
        priority=MemoryPriority.MEDIUM,
        created_at=now,
        updated_at=now,
        source=MemorySource.MANUAL,
        confidence=0.5,
    )
    with pytest.raises(ValueError):
        MemoryListResult(items=[entry], next_cursor=None, has_more=True)


def test_memory_audit_event_defaults_timestamp() -> None:
    event = MemoryAuditEvent(
        action="memory_create",
        actor_id="root_sys1",
        scope=MemoryScope.AGENT,
        namespace="root",
        resource_id="mem-1",
        success=True,
        details={},
    )
    assert event.timestamp.tzinfo is not None
