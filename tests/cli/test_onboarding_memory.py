from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from src.cyberagent.cli import onboarding_memory
from src.cyberagent.memory.models import MemoryLayer, MemoryPriority, MemoryScope
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

    class FakeService:
        def create_entries(self, *, actor, requests) -> None:  # type: ignore[no-untyped-def]
            recorded["actor"] = actor
            recorded["requests"] = requests

    monkeypatch.setattr(
        onboarding_memory, "get_system_by_type", lambda *_: FakeSystem()
    )
    monkeypatch.setattr(
        onboarding_memory, "_build_memory_service", lambda: FakeService()
    )

    onboarding_memory.store_onboarding_memory(1, summary_path)

    assert "actor" in recorded
    requests = cast(list, recorded["requests"])
    request = requests[0]
    assert request.content == "Profile details"
    assert request.scope == MemoryScope.GLOBAL
    assert request.priority == MemoryPriority.HIGH
    assert request.layer == MemoryLayer.LONG_TERM
    assert request.owner_agent_id == "System4/root"


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

    class FakeService:
        def create_entries(self, *, actor, requests) -> None:  # type: ignore[no-untyped-def]
            raise PermissionError("nope")

    monkeypatch.setattr(
        onboarding_memory, "get_system_by_type", lambda *_: FakeSystem()
    )
    monkeypatch.setattr(
        onboarding_memory, "_build_memory_service", lambda: FakeService()
    )

    onboarding_memory.store_onboarding_memory(1, summary_path)
    captured = capsys.readouterr()
    assert "unable to store onboarding summary" in captured.out
