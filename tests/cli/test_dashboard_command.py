from __future__ import annotations

import subprocess
import sys
from typing import Sequence, cast

import pytest

from src.cyberagent.cli import cyberagent


def test_build_parser_includes_dashboard_command() -> None:
    parser = cyberagent.build_parser()
    parsed = parser.parse_args(["dashboard"])
    assert parsed.command == "dashboard"


def test_dashboard_command_starts_streamlit(monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.setattr(
        cyberagent.dashboard_launcher,
        "resolve_dashboard_python",
        lambda: sys.executable,
    )
    monkeypatch.setattr(subprocess, "run", fake_run)

    exit_code = cyberagent.main(["dashboard"])

    assert exit_code == 0
    cmd = cast(Sequence[str], recorded["cmd"])
    assert list(cmd[:3]) == [sys.executable, "-m", "streamlit"]
    assert cmd[3] == "run"
    assert str(cmd[4]).endswith("src/cyberagent/ui/dashboard.py")


def test_dashboard_command_requires_streamlit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_run(*_: object, **__: object) -> None:
        raise AssertionError(
            "subprocess.run should not be called when streamlit is missing"
        )

    monkeypatch.setattr(
        cyberagent.dashboard_launcher, "resolve_dashboard_python", lambda: None
    )
    monkeypatch.setattr(subprocess, "run", fail_run)

    exit_code = cyberagent.main(["dashboard"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Streamlit is not installed" in captured.err
    assert "python3 -m pip install -e ." in captured.err


def test_dashboard_command_uses_venv_python_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}
    venv_python = "/tmp/project/.venv/bin/python"

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

    monkeypatch.setattr(
        cyberagent.dashboard_launcher, "resolve_dashboard_python", lambda: venv_python
    )
    monkeypatch.setattr(subprocess, "run", fake_run)

    exit_code = cyberagent.main(["dashboard"])

    assert exit_code == 0
    cmd = cast(Sequence[str], recorded["cmd"])
    assert cmd[0] == venv_python
    assert list(cmd[1:3]) == ["-m", "streamlit"]
