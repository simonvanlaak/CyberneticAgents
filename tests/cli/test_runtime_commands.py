from __future__ import annotations

import argparse
import signal
from pathlib import Path

import pytest

from src.cyberagent.cli.commands import runtime_commands


@pytest.mark.asyncio
async def test_handle_stop_terminates_background_runtime_and_clears_pid_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pid_file = tmp_path / "cyberagent.pid"
    pid_file.write_text("4242", encoding="utf-8")
    monkeypatch.setattr(runtime_commands, "RUNTIME_PID_FILE", pid_file)

    alive = {"value": True}
    kill_calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))
        if sig == 0:
            if alive["value"]:
                return
            raise ProcessLookupError
        if sig == signal.SIGTERM:
            alive["value"] = False
            return
        raise AssertionError(f"Unexpected signal: {sig}")

    monkeypatch.setattr(runtime_commands.os, "kill", fake_kill)
    monkeypatch.setattr(runtime_commands.time, "sleep", lambda _: None)
    monkeypatch.setattr(runtime_commands, "_pid_looks_like_runtime", lambda pid: True)
    monkeypatch.setattr(runtime_commands, "_discover_runtime_pids", lambda: [4242])

    stop_runtime_calls = {"count": 0}

    async def fake_stop_runtime() -> None:
        stop_runtime_calls["count"] += 1

    monkeypatch.setattr(runtime_commands, "stop_runtime", fake_stop_runtime)

    exit_code = await runtime_commands._handle_stop(argparse.Namespace())

    assert exit_code == 0
    assert stop_runtime_calls["count"] == 1
    assert (4242, signal.SIGTERM) in kill_calls
    assert not pid_file.exists()


@pytest.mark.asyncio
async def test_handle_stop_removes_stale_pid_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pid_file = tmp_path / "cyberagent.pid"
    pid_file.write_text("9999", encoding="utf-8")
    monkeypatch.setattr(runtime_commands, "RUNTIME_PID_FILE", pid_file)

    def fake_kill(pid: int, sig: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr(runtime_commands.os, "kill", fake_kill)
    monkeypatch.setattr(runtime_commands, "_pid_looks_like_runtime", lambda pid: True)
    monkeypatch.setattr(runtime_commands, "_discover_runtime_pids", lambda: [9999])

    async def fake_stop_runtime() -> None:
        return None

    monkeypatch.setattr(runtime_commands, "stop_runtime", fake_stop_runtime)

    exit_code = await runtime_commands._handle_stop(argparse.Namespace())

    assert exit_code == 0
    assert not pid_file.exists()


@pytest.mark.asyncio
async def test_handle_stop_terminates_all_discovered_runtime_pids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pid_file = tmp_path / "cyberagent.pid"
    pid_file.write_text("4242", encoding="utf-8")
    monkeypatch.setattr(runtime_commands, "RUNTIME_PID_FILE", pid_file)
    monkeypatch.setattr(
        runtime_commands, "_discover_runtime_pids", lambda: [1111, 2222]
    )
    monkeypatch.setattr(runtime_commands, "_pid_looks_like_runtime", lambda pid: True)

    alive = {1111: True, 2222: True}
    kill_calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))
        if sig == 0:
            if alive.get(pid, False):
                return
            raise ProcessLookupError
        if sig == signal.SIGTERM:
            alive[pid] = False
            return
        raise AssertionError(f"Unexpected signal: {sig}")

    monkeypatch.setattr(runtime_commands.os, "kill", fake_kill)
    monkeypatch.setattr(runtime_commands.time, "sleep", lambda _: None)

    async def fake_stop_runtime() -> None:
        return None

    monkeypatch.setattr(runtime_commands, "stop_runtime", fake_stop_runtime)

    exit_code = await runtime_commands._handle_stop(argparse.Namespace())

    assert exit_code == 0
    assert (1111, signal.SIGTERM) in kill_calls
    assert (2222, signal.SIGTERM) in kill_calls
