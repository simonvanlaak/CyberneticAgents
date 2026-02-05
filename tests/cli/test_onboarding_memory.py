from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from src.cyberagent.cli import onboarding_memory
from src.cyberagent.memory.models import MemoryLayer, MemoryPriority, MemorySource
from src.cyberagent.tools.memory_crud import (
    MemoryCrudArgs,
    MemoryCrudError,
    MemoryCrudResponse,
)
from src.enums import SystemType


def test_store_onboarding_memory_no_path(tmp_path: Path) -> None:
    onboarding_memory.store_onboarding_memory(1, None)


def test_store_onboarding_memory_missing_file(tmp_path: Path) -> None:
    onboarding_memory.store_onboarding_memory(1, tmp_path / "missing.txt")


def test_store_onboarding_memory_unreadable_path(tmp_path: Path) -> None:
    onboarding_memory.store_onboarding_memory(1, tmp_path)


def test_store_onboarding_memory_empty_summary(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.txt"
    summary_path.write_text("   ", encoding="utf-8")
    onboarding_memory.store_onboarding_memory(1, summary_path)


def test_store_onboarding_memory_missing_system4(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "summary.txt"
    summary_path.write_text("Profile details", encoding="utf-8")
    monkeypatch.setattr(onboarding_memory, "get_system_by_type", lambda *_: None)
    onboarding_memory.store_onboarding_memory(1, summary_path)


def test_store_onboarding_memory_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "summary.txt"
    summary_path.write_text("Profile details", encoding="utf-8")

    class FakeSystem:
        id = 10
        type = SystemType.INTELLIGENCE
        agent_id_str = "System4/root"

    recorded: dict[str, Any] = {}

    class FakeTool:
        async def run(self, args: MemoryCrudArgs, _token) -> MemoryCrudResponse:  # type: ignore[no-untyped-def]
            recorded["args"] = args
            return MemoryCrudResponse(
                items=[], next_cursor=None, has_more=False, errors=[]
            )

    monkeypatch.setattr(
        onboarding_memory, "get_system_by_type", lambda *_: FakeSystem()
    )
    monkeypatch.setattr(onboarding_memory, "_build_memory_tool", lambda *_: FakeTool())

    onboarding_memory.store_onboarding_memory(1, summary_path)

    args = cast(MemoryCrudArgs, recorded["args"])
    assert args.action == "create"
    assert args.scope == "global"
    assert args.namespace == "user"
    items = cast(list, args.items)
    item = items[0]
    assert item["content"] == "Profile details"
    assert item["priority"] == MemoryPriority.HIGH.value
    assert item["layer"] == MemoryLayer.LONG_TERM.value
    assert item["owner_agent_id"] == "System4/root"


def test_store_onboarding_memory_warns_on_failure(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "summary.txt"
    summary_path.write_text("Profile details", encoding="utf-8")

    class FakeSystem:
        id = 10
        type = SystemType.INTELLIGENCE
        agent_id_str = "System4/root"

    class FakeTool:
        async def run(self, args: MemoryCrudArgs, _token) -> MemoryCrudResponse:  # type: ignore[no-untyped-def]
            return MemoryCrudResponse(
                items=[],
                next_cursor=None,
                has_more=False,
                errors=[
                    MemoryCrudError(
                        code="FORBIDDEN",
                        message="nope",
                        details=None,
                    )
                ],
            )

    monkeypatch.setattr(
        onboarding_memory, "get_system_by_type", lambda *_: FakeSystem()
    )
    monkeypatch.setattr(onboarding_memory, "_build_memory_tool", lambda *_: FakeTool())

    onboarding_memory.store_onboarding_memory(1, summary_path)
    captured = capsys.readouterr()
    assert "unable to store onboarding summary" in captured.out


def test_store_onboarding_memory_entry_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSystem:
        id = 10
        type = SystemType.INTELLIGENCE
        agent_id_str = "System4/root"

    recorded: dict[str, Any] = {}

    class FakeTool:
        async def run(self, args: MemoryCrudArgs, _token) -> MemoryCrudResponse:  # type: ignore[no-untyped-def]
            recorded["args"] = args
            return MemoryCrudResponse(
                items=[], next_cursor=None, has_more=False, errors=[]
            )

    monkeypatch.setattr(
        onboarding_memory, "get_system_by_type", lambda *_: FakeSystem()
    )
    monkeypatch.setattr(onboarding_memory, "_build_memory_tool", lambda *_: FakeTool())

    onboarding_memory.store_onboarding_memory_entry(
        team_id=1,
        content="Profile details",
        tags=["onboarding", "profile_link"],
        source=MemorySource.TOOL,
        priority=MemoryPriority.MEDIUM,
        layer=MemoryLayer.SESSION,
    )

    args = cast(MemoryCrudArgs, recorded["args"])
    assert args.action == "create"
    assert args.scope == "global"
    assert args.namespace == "user"
    items = cast(list, args.items)
    item = items[0]
    assert item["content"] == "Profile details"
    assert item["source"] == MemorySource.TOOL.value
    assert item["priority"] == MemoryPriority.MEDIUM.value
    assert item["layer"] == MemoryLayer.SESSION.value
