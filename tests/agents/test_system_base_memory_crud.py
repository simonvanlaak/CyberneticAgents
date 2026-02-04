from typing import List

from unittest.mock import MagicMock

import pytest

import sys

sys.modules.setdefault("langfuse", MagicMock())

from src.agents import system_base as system_base_module  # noqa: E402
from src.agents.system_base import SystemBase  # noqa: E402
from src.enums import SystemType  # noqa: E402


class DummyMemoryCrudTool:
    def __init__(self, agent_id) -> None:
        self.agent_id = agent_id


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

    def _get_systems_by_type(self, type: SystemType) -> List:
        return []


def _configure_system_base(monkeypatch: pytest.MonkeyPatch, *, allowed: bool) -> None:
    monkeypatch.setenv("CYBERAGENT_ACTIVE_TEAM_ID", "1")
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
    monkeypatch.setattr(
        system_base_module,
        "get_system_from_agent_id",
        lambda agent_id: type("S", (), {"id": 1})(),
    )
    monkeypatch.setattr(
        system_base_module.system_service,
        "can_execute_skill",
        lambda system_id, skill_name: (allowed, None),
    )
    monkeypatch.setattr(system_base_module, "MemoryCrudTool", DummyMemoryCrudTool)
    monkeypatch.setattr(system_base_module, "AssistantAgent", DummyAssistantAgent)


def test_memory_crud_tool_not_added_without_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_system_base(monkeypatch, allowed=False)
    system = DummySystem()
    assert not any(
        isinstance(tool, DummyMemoryCrudTool) for tool in system.available_tools
    )


def test_memory_crud_tool_added_with_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_system_base(monkeypatch, allowed=True)
    system = DummySystem()
    assert any(isinstance(tool, DummyMemoryCrudTool) for tool in system.available_tools)
