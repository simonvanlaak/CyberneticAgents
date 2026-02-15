from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.cli.commands import runtime_commands
from src.cyberagent.cli import runtime_start_health


class _ExitedProc:
    def __init__(self, pid: int, returncode: int) -> None:
        self.pid = pid
        self._returncode = returncode

    def poll(self) -> int:
        return self._returncode


def _patch_fast_time(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter([0.0, 0.1, 0.2, 0.3])
    monkeypatch.setattr(runtime_start_health.time, "time", lambda: next(ticks, 1.0))
    monkeypatch.setattr(runtime_start_health.time, "sleep", lambda *_: None)


def test_onboarding_start_runtime_fails_when_process_exits_early(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pid_file = tmp_path / "cyberagent.pid"
    monkeypatch.setattr(onboarding_cli, "RUNTIME_PID_FILE", pid_file)
    monkeypatch.setattr(onboarding_cli, "RUNTIME_STARTUP_GRACE_SECONDS", 1.0)
    _patch_fast_time(monkeypatch)
    monkeypatch.setattr(onboarding_cli, "load_runtime_pid", lambda *_: None)
    monkeypatch.setattr(
        onboarding_cli,
        "resolve_runtime_db_url",
        lambda *_args, **_kwargs: "sqlite:///x",
    )
    monkeypatch.setattr(onboarding_cli, "get_secret", lambda *_: None)
    monkeypatch.setattr(
        onboarding_cli.subprocess,
        "Popen",
        lambda *_args, **_kwargs: _ExitedProc(pid=111, returncode=7),
    )

    result = onboarding_cli._start_runtime_after_onboarding(team_id=1)

    assert result == -1
    assert not pid_file.exists()
    assert "Runtime exited during startup" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_runtime_commands_handle_start_fails_when_process_exits_early(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pid_file = tmp_path / "cyberagent.pid"
    monkeypatch.setattr(runtime_commands, "RUNTIME_PID_FILE", pid_file)
    monkeypatch.setattr(runtime_commands, "RUNTIME_STARTUP_GRACE_SECONDS", 1.0)
    _patch_fast_time(monkeypatch)
    monkeypatch.setattr(runtime_commands, "init_db", lambda: None)
    monkeypatch.setattr(runtime_commands, "_require_existing_team", lambda: 1)
    queue_calls: list[int] = []
    monkeypatch.setattr(
        runtime_commands,
        "queue_in_progress_initiatives",
        lambda team_id: queue_calls.append(team_id),
    )
    monkeypatch.setattr(
        runtime_commands.subprocess,
        "Popen",
        lambda *_args, **_kwargs: _ExitedProc(pid=222, returncode=9),
    )

    code = await runtime_commands._handle_start(argparse.Namespace(message=None))

    assert code == 1
    assert queue_calls == []
    assert not pid_file.exists()
    assert "Runtime exited during startup" in capsys.readouterr().out


def test_runtime_commands_start_background_returns_none_when_process_exits_early(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pid_file = tmp_path / "cyberagent.pid"
    monkeypatch.setattr(runtime_commands, "RUNTIME_PID_FILE", pid_file)
    monkeypatch.setattr(runtime_commands, "RUNTIME_STARTUP_GRACE_SECONDS", 1.0)
    _patch_fast_time(monkeypatch)
    monkeypatch.setattr(runtime_commands, "init_db", lambda: None)
    monkeypatch.setattr(runtime_commands, "_require_existing_team", lambda: 1)
    monkeypatch.setattr(
        runtime_commands.subprocess,
        "Popen",
        lambda *_args, **_kwargs: _ExitedProc(pid=333, returncode=3),
    )

    pid = runtime_commands._start_runtime_background()

    assert pid is None
    assert not pid_file.exists()
    assert "Runtime exited during startup" in capsys.readouterr().out
