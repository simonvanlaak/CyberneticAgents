from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence, cast

import pytest

from src.cyberagent.cli import cyberagent


def test_start_queues_in_progress_initiatives(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded: dict[str, object] = {}

    class DummyProcess:
        def __init__(
            self,
            cmd: Sequence[str],
            *,
            env: dict[str, str],
            stdout: Any,
            stderr: Any,
            close_fds: bool,
        ) -> None:
            recorded["cmd"] = cmd
            recorded["env"] = env
            self.pid = 7788

        def poll(self) -> None:
            return None

    called: dict[str, int] = {}

    def _fake_queue(team_id: int) -> int:
        called["team_id"] = team_id
        return 1

    monkeypatch.setenv("CYBERAGENT_TEST_NO_RUNTIME", "")
    monkeypatch.setattr(subprocess, "Popen", DummyProcess)
    monkeypatch.setattr(cyberagent, "get_last_team_id", lambda: 9)
    monkeypatch.setattr(cyberagent, "init_db", lambda: None)
    monkeypatch.setattr(cyberagent, "queue_in_progress_initiatives", _fake_queue)
    target_pid = tmp_path / "serve.pid"
    monkeypatch.setattr(cyberagent, "RUNTIME_PID_FILE", target_pid)

    exit_code = cyberagent.main(["start"])

    assert exit_code == 0
    recorded_cmd = cast(Sequence[str], recorded["cmd"])
    assert recorded_cmd[0] == sys.executable
    assert called["team_id"] == 9
