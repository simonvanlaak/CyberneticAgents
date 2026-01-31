from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
from typing import Sequence

import pytest

from src.cli import cyberagent
from src.cli_session import AnsweredQuestion, PendingQuestion


@pytest.mark.parametrize(
    "command,label",
    [
        (["start"], "start"),
        (["stop"], "stop"),
        (["status"], "status"),
        (["suggest"], "suggest"),
        (["inbox"], "inbox"),
        (["watch"], "watch"),
        (["logs"], "logs"),
        (["config", "view"], "config"),
        (["login"], "login"),
    ],
)
def test_build_parser_includes_commands(command: Sequence[str], label: str) -> None:
    parser = cyberagent.build_parser()
    parsed = parser.parse_args(command)
    assert parsed.command == label


def test_start_command_invokes_headless_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, str | None] = {}

    async def fake_headless_session(initial_message: str | None = None) -> None:
        called["initial_message"] = initial_message

    monkeypatch.setattr(cyberagent, "run_headless_session", fake_headless_session)
    exit_code = cyberagent.main(["start", "--message", "ready"])
    assert exit_code == 0
    assert called["initial_message"] == "ready"


def test_status_command_delegates_to_status_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Sequence[str]] = {}

    def fake_status_main(argv: Sequence[str]) -> int:
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cyberagent, "status_main", fake_status_main)
    exit_code = cyberagent.main(["status", "--json"])
    assert exit_code == 0
    assert captured["argv"] == ["--json"]


def test_parse_suggestion_requires_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    args = argparse.Namespace(payload=None, file=None, format="json")
    fake_stdin = io.StringIO("")
    fake_stdin.isatty = lambda: True
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    with pytest.raises(ValueError):
        cyberagent._parse_suggestion_args(args)


def test_parse_suggestion_json_payload() -> None:
    args = argparse.Namespace(payload='{"foo": "bar"}', file=None, format="json")
    parsed = cyberagent._parse_suggestion_args(args)
    assert parsed.payload_object == {"foo": "bar"}
    assert '"foo": "bar"' in parsed.payload_text


def test_handle_inbox_prints_entries(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pending = [
        PendingQuestion(
            question_id=1, content="Need info", asked_by="System4", created_at=0
        )
    ]
    answered = [
        AnsweredQuestion(
            question_id=2,
            content="What should we build?",
            asked_by="System4",
            created_at=0,
            answer="A CLI",
            answered_at=1,
        )
    ]
    monkeypatch.setattr(cyberagent, "get_pending_questions", lambda: pending)
    monkeypatch.setattr(cyberagent, "get_answered_questions", lambda: answered)
    result = cyberagent._handle_inbox(argparse.Namespace(answered=True))
    captured = capsys.readouterr()
    assert result == 0
    assert "Pending questions" in captured.out
    assert "Answered questions" in captured.out
    assert "[1] Need info" in captured.out
    assert "[2] What should we build?" in captured.out


@pytest.mark.asyncio
async def test_handle_watch_prints_pending(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    question = PendingQuestion(
        question_id=7, content="Watch this", asked_by="System4", created_at=0
    )
    monkeypatch.setattr(cyberagent, "get_pending_questions", lambda: [question])

    async def fake_sleep(interval: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cyberagent.asyncio, "sleep", fake_sleep)
    await cyberagent._handle_watch(argparse.Namespace(interval=0.1))
    captured = capsys.readouterr()
    assert "[7] Watch this" in captured.out


def test_filter_logs_applies_pattern_and_limit() -> None:
    lines = ["alpha", "Beta", "gamma", "delta"]
    filtered = cyberagent._filter_logs(lines, "a", 2)
    assert filtered == ["gamma", "delta"]


def test_handle_config_displays_teams(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from types import SimpleNamespace

    class DummySystem:
        def __init__(self, type_name: str, agent_id: str) -> None:
            self.type = SimpleNamespace(name=type_name)
            self.agent_id_str = agent_id

    class DummyTeam:
        def __init__(self) -> None:
            self.name = "Engineering"
            self.id = 99
            self.systems = [DummySystem("SYSTEM4", "System4/root")]

    class DummyQuery:
        def __init__(self, teams: list[DummyTeam]) -> None:
            self._teams = teams

        def order_by(self, *args: object, **kwargs: object) -> "DummyQuery":
            return self

        def all(self) -> list[DummyTeam]:
            return self._teams

    class DummySession:
        def __init__(self, teams: list[DummyTeam]) -> None:
            self._teams = teams

        def query(self, model: object) -> DummyQuery:
            return DummyQuery(self._teams)

        def close(self) -> None:
            return None

    def fake_get_db() -> Sequence[DummySession]:
        yield DummySession([DummyTeam()])

    monkeypatch.setattr(cyberagent, "init_db", lambda: None)
    monkeypatch.setattr(cyberagent, "get_db", fake_get_db)
    result = cyberagent._handle_config(argparse.Namespace(config_command="view"))
    captured = capsys.readouterr()
    assert result == 0
    assert "Team: Engineering (id=99)" in captured.out
    assert "SYSTEM4 (System4/root)" in captured.out


def test_help_lists_commands() -> None:
    help_text = cyberagent.build_parser().format_help()
    assert "start" in help_text
    assert "Boot the VSM runtime." in help_text
    for command in (
        "stop",
        "status",
        "suggest",
        "inbox",
        "watch",
        "logs",
        "config",
        "login",
    ):
        assert command in help_text


def test_no_args_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cyberagent.main([])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "usage" in captured.out.lower()


def test_help_command_prints_general(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cyberagent.main(["help"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "usage" in captured.out.lower()
    assert "cyberagent" in captured.out


def test_help_command_prints_start(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cyberagent.main(["help", "start"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Boot the VSM runtime." in captured.out


def test_python_module_start_uses_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    env = os.environ.copy()
    env["CYBERAGENT_TEST_NO_RUNTIME"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.cyberagent", "start"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=5,
    )
    assert result.returncode == 0
    assert "Runtime start stubbed" in result.stdout
