from __future__ import annotations

import subprocess
import sys
from typing import Sequence, cast

import pytest

from src.cyberagent.cli import cyberagent


def test_build_parser_includes_ui_command() -> None:
    parser = cyberagent.build_parser()
    parsed = parser.parse_args(["ui"])
    assert parsed.command == "ui"


def test_ui_command_starts_streamlit(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    class DummyCompleted:
        returncode = 0

    def fake_run(
        cmd: Sequence[str],
        *,
        check: bool,
        env: dict[str, str],
    ) -> DummyCompleted:
        recorded["cmd"] = cmd
        recorded["check"] = check
        recorded["env"] = env
        return DummyCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)

    exit_code = cyberagent.main(["ui"])

    assert exit_code == 0
    cmd = cast(Sequence[str], recorded["cmd"])
    assert list(cmd[:3]) == [sys.executable, "-m", "streamlit"]
    assert cmd[3] == "run"
    assert str(cmd[4]).endswith("src/cyberagent/ui/dashboard.py")
