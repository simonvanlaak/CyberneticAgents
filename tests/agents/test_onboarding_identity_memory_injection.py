from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId

from src.agents.system_base_mixin import SystemBaseMixin
from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryLayer,
    MemoryListResult,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.enums import SystemType


def _make_entry(entry_id: str) -> MemoryEntry:
    now = datetime.now(timezone.utc)
    return MemoryEntry(
        id=entry_id,
        scope=MemoryScope.GLOBAL,
        namespace="user",
        owner_agent_id="System4/root",
        content="User: Simon. Links: https://github.com/simonvanlaak",
        tags=["onboarding", "user_profile"],
        priority=MemoryPriority.HIGH,
        created_at=now,
        updated_at=now,
        expires_at=None,
        source=MemorySource.IMPORT,
        confidence=0.7,
        layer=MemoryLayer.LONG_TERM,
    )


class _DummyAgent(SystemBaseMixin):
    def __init__(self) -> None:
        self.agent_id = AgentId.from_str("System1/root")
        self.team_id = 1
        self.name = "System1_root"
        self.identity_prompt = ""
        self.responsibility_prompts = []
        self.tools = []
        self._agent = MagicMock()
        self._last_system_messages = []
        self._session_recorder = None
        self.publish_message = MagicMock()


def test_system1_identity_task_injects_onboarding_profile_by_tags(monkeypatch) -> None:
    """Ensure identity-collection tasks can recall onboarding profile even if semantic query misses."""

    # Force a valid system record for the agent so _build_memory_context proceeds.
    class _SystemRecord:
        agent_id_str = "System1/root"
        id = 1
        team_id = 1
        type = SystemType.OPERATION

    monkeypatch.setattr(
        "src.agents.system_base_mixin.get_system_from_agent_id",
        lambda _agent_id: _SystemRecord(),
    )

    calls: list[dict[str, object]] = []

    def _fake_search_entries(*_args, tags=None, query_text=None, **kwargs):  # type: ignore[no-untyped-def]
        calls.append({"tags": tags, "query_text": query_text, **kwargs})
        # Simulate semantic search returning nothing, then tag search returning the profile.
        if tags:
            return MemoryListResult(
                items=[_make_entry("mem-onboarding")], next_cursor=None, has_more=False
            )
        return MemoryListResult(items=[], next_cursor=None, has_more=False)

    monkeypatch.setattr(
        "src.agents.system_base_mixin.MemoryRetrievalService.search_entries",
        _fake_search_entries,
    )

    agent = _DummyAgent()
    message = TextMessage(
        content="Collect user identity and links", source="System3/root"
    )

    context = agent._build_memory_context(message)

    assert any("mem-onboarding" in line for line in context)
    assert any(
        call.get("tags") for call in calls
    ), "expected a tag-based fallback query"
