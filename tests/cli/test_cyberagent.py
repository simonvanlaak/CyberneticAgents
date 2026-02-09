from __future__ import annotations

import argparse
import asyncio
import io
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterator, Sequence, cast

import pytest
from autogen_core import AgentId

from src.cyberagent.cli import cyberagent
from src.cyberagent.cli import log_filters
from src.cyberagent.cli import transcribe as transcribe_cli
from src.cyberagent.cli.env_loader import load_op_service_account_token
from src.cyberagent.channels.inbox import InboxEntry


@pytest.mark.parametrize(
    "command,label",
    [
        (["start"], "start"),
        (["restart"], "restart"),
        (["stop"], "stop"),
        (["status"], "status"),
        (["onboarding"], "onboarding"),
        (["suggest"], "suggest"),
        (["inbox"], "inbox"),
        (["watch"], "watch"),
        (["logs"], "logs"),
        (["transcribe", "audio.wav"], "transcribe"),
        (["config", "view"], "config"),
        (["login"], "login"),
        (["reset", "--yes"], "reset"),
    ],
)
def test_build_parser_includes_commands(command: Sequence[str], label: str) -> None:
    parser = cyberagent.build_parser()
    parsed = parser.parse_args(command)
    assert parsed.command == label


def test_build_parser_includes_dev_system_run() -> None:
    parser = cyberagent.build_parser()
    parsed = parser.parse_args(["dev", "system-run", "System4/root", "hello"])
    assert parsed.command == "dev"
    assert parsed.dev_command == "system-run"
    assert parsed.system_id == "System4/root"
    assert parsed.message == "hello"


def test_start_command_uses_background_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, bool] = {"headless": False}

    async def fake_headless_session(initial_message: str | None = None) -> None:
        called["headless"] = True

    class DummyProcess:
        def __init__(self, cmd: Sequence[str], **kwargs: Any) -> None:
            self.pid = 1

    monkeypatch.setattr(cyberagent, "run_headless_session", fake_headless_session)
    monkeypatch.setattr(subprocess, "Popen", DummyProcess)
    exit_code = cyberagent.main(["start", "--message", "ready"])
    assert exit_code == 0
    assert called["headless"] is False


def test_restart_command_calls_stop_then_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_stop(_: argparse.Namespace) -> int:
        calls.append("stop")
        return 0

    async def fake_start(_: argparse.Namespace) -> int:
        calls.append("start")
        return 0

    monkeypatch.setattr(cyberagent, "_handle_stop", fake_stop)
    monkeypatch.setattr(cyberagent, "_handle_start", fake_start)

    exit_code = cyberagent.main(["restart"])
    assert exit_code == 0
    assert calls == ["stop", "start"]


def test_restart_command_accepts_message_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str | None] = {"message": None}

    async def fake_stop(_: argparse.Namespace) -> int:
        return 0

    async def fake_start(args: argparse.Namespace) -> int:
        captured["message"] = args.message
        return 0

    monkeypatch.setattr(cyberagent, "_handle_stop", fake_stop)
    monkeypatch.setattr(cyberagent, "_handle_start", fake_start)

    exit_code = cyberagent.main(["restart", "--message", "ready"])
    assert exit_code == 0
    assert captured["message"] == "ready"


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
    args = argparse.Namespace(message=None, payload=None, file=None, format="json")
    fake_stdin = io.StringIO("")
    fake_stdin.isatty = lambda: True
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    with pytest.raises(ValueError):
        cyberagent._parse_suggestion_args(args)


def test_parse_suggestion_json_payload() -> None:
    args = argparse.Namespace(
        message=None, payload='{"foo": "bar"}', file=None, format="json"
    )
    parsed = cyberagent._parse_suggestion_args(args)
    assert parsed.payload_object == {"foo": "bar"}
    assert '"foo": "bar"' in parsed.payload_text


def test_parse_suggestion_positional_message() -> None:
    args = argparse.Namespace(
        message="Run this and that", payload=None, file=None, format="json"
    )
    parsed = cyberagent._parse_suggestion_args(args)
    assert parsed.payload_object == "Run this and that"


def test_handle_suggest_invalid_payload_prints_guidance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(message=None, payload=None, file=None, format="json")
    fake_stdin = io.StringIO("")
    fake_stdin.isatty = lambda: True
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    exit_code = cyberagent._handle_suggest(args)
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Invalid payload" in captured.err
    assert "cyberagent suggest" in captured.err
    assert "--file" in captured.err


def test_handle_suggest_enqueues_payload(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    recorded: dict[str, object] = {}

    def fake_enqueue(payload_text: str) -> None:
        recorded["payload"] = payload_text

    monkeypatch.setattr(cyberagent, "enqueue_suggestion", fake_enqueue)
    monkeypatch.setattr(cyberagent, "_ensure_background_runtime", lambda: 1234)

    args = argparse.Namespace(message=None, payload="hello", file=None, format="json")
    exit_code = cyberagent._handle_suggest(args)

    output = capsys.readouterr().out
    assert exit_code == 0
    assert recorded["payload"] == "hello"
    assert "Runtime active in background (pid 1234)." in output
    assert "Suggestion queued for System4." in output


def test_handle_suggest_requires_team(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cyberagent, "get_last_team_id", lambda: None)
    monkeypatch.setattr(cyberagent, "enqueue_suggestion", lambda *_: None)
    monkeypatch.setattr(cyberagent, "_ensure_background_runtime", lambda: 1234)

    args = argparse.Namespace(message="hello", payload=None, file=None, format="json")
    exit_code = cyberagent._handle_suggest(args)

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "cyberagent onboarding" in output


def test_handle_transcribe_prints_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")

    class _Result:
        text = "hello world"
        low_confidence = False

    def fake_transcribe(file_path: Path) -> _Result:
        assert file_path == audio_path
        return _Result()

    monkeypatch.setattr(transcribe_cli, "transcribe_file", fake_transcribe)

    exit_code = cyberagent.main(["transcribe", str(audio_path)])

    output = capsys.readouterr().out.strip().splitlines()
    assert exit_code == 0
    assert output[-1] == "hello world"


def test_handle_transcribe_warns_on_low_confidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")

    class _Result:
        text = "noisy audio"
        low_confidence = True

    def fake_transcribe(file_path: Path) -> _Result:
        assert file_path == audio_path
        return _Result()

    monkeypatch.setattr(transcribe_cli, "transcribe_file", fake_transcribe)

    exit_code = cyberagent.main(["transcribe", str(audio_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "low" in captured.err.lower()


def test_handle_inbox_prints_entries(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    entries = [
        InboxEntry(
            entry_id=1,
            kind="system_question",
            content="Need info",
            created_at=0,
            channel="cli",
            session_id="cli-main",
            asked_by="System4",
            status="pending",
        ),
        InboxEntry(
            entry_id=2,
            kind="system_response",
            content="What should we build?",
            created_at=0,
            channel="cli",
            session_id="cli-main",
        ),
    ]
    monkeypatch.setattr(
        cyberagent,
        "list_inbox_entries",
        lambda *_, **__: entries,
    )
    result = cyberagent._handle_inbox(
        argparse.Namespace(
            channel=None,
            session_id=None,
            telegram_chat_id=None,
            telegram_user_id=None,
        )
    )
    captured = capsys.readouterr()
    assert result == 0
    assert "System questions" in captured.out
    assert "System responses" in captured.out
    assert "[1] Need info" in captured.out
    assert "channel=cli" in captured.out
    assert "[2] What should we build?" in captured.out


def test_handle_inbox_requires_team(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cyberagent, "get_last_team_id", lambda: None)
    result = cyberagent._handle_inbox(
        argparse.Namespace(
            channel=None,
            session_id=None,
            telegram_chat_id=None,
            telegram_user_id=None,
        )
    )
    captured = capsys.readouterr()
    assert result == 1
    assert "cyberagent onboarding" in captured.out


def test_handle_inbox_warns_when_telegram_unavailable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    entries = [
        InboxEntry(
            entry_id=1,
            kind="user_prompt",
            content="Ping",
            created_at=0,
            channel="telegram",
            session_id="telegram:chat-1:user-2",
        )
    ]
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(cyberagent, "get_last_team_id", lambda: "team-1")
    monkeypatch.setattr(cyberagent, "list_inbox_entries", lambda *_, **__: entries)

    result = cyberagent._handle_inbox(
        argparse.Namespace(
            channel=None,
            session_id=None,
            telegram_chat_id=None,
            telegram_user_id=None,
        )
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "Telegram delivery disabled" in captured.out


@pytest.mark.asyncio
async def test_handle_watch_prints_pending(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    entry = InboxEntry(
        entry_id=7,
        kind="system_question",
        content="Watch this",
        created_at=0,
        channel="cli",
        session_id="cli-main",
        asked_by="System4",
        status="pending",
    )
    monkeypatch.setattr(cyberagent, "list_inbox_entries", lambda *_, **__: [entry])

    async def fake_sleep(interval: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cyberagent.asyncio, "sleep", fake_sleep)
    await cyberagent._handle_watch(
        argparse.Namespace(
            interval=0.1,
            channel=None,
            session_id=None,
            telegram_chat_id=None,
            telegram_user_id=None,
        )
    )
    captured = capsys.readouterr()
    assert "[7] Watch this" in captured.out


@pytest.mark.asyncio
async def test_handle_watch_requires_team(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cyberagent, "get_last_team_id", lambda: None)
    result = await cyberagent._handle_watch(
        argparse.Namespace(
            interval=0.1,
            channel=None,
            session_id=None,
            telegram_chat_id=None,
            telegram_user_id=None,
        )
    )
    captured = capsys.readouterr()
    assert result == 1
    assert "cyberagent onboarding" in captured.out


def test_filter_logs_applies_pattern_and_limit() -> None:
    lines = ["alpha", "Beta", "gamma", "delta"]
    filtered = log_filters.filter_logs(lines, "a", 2, None)
    assert filtered == ["gamma", "delta"]


def test_filter_logs_with_levels() -> None:
    lines = [
        "2025-01-01 00:00:00.000 INFO [x] ok",
        "2025-01-01 00:00:01.000 WARNING [x] warn",
        "2025-01-01 00:00:02.000 ERROR [x] boom",
    ]
    levels = log_filters.resolve_log_levels(["error,warning"], default_to_errors=False)
    assert levels == {"ERROR", "WARNING"}
    filtered = log_filters.filter_logs(lines, None, 10, levels)
    assert filtered == [
        "2025-01-01 00:00:01.000 WARNING [x] warn",
        "2025-01-01 00:00:02.000 ERROR [x] boom",
    ]


def test_resolve_log_levels_defaults_to_errors() -> None:
    levels = log_filters.resolve_log_levels(None, default_to_errors=True)
    assert levels == {"ERROR", "CRITICAL"}


def test_handle_logs_without_level_shows_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "runtime_20250101_000000.log"
    log_file.write_text(
        "2025-01-01 00:00:00.000 INFO [x] ok\n"
        "2025-01-01 00:00:01.000 ERROR [x] boom\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cyberagent, "LOGS_DIR", log_dir)

    args = argparse.Namespace(
        filter=None,
        level=None,
        follow=False,
        limit=200,
    )

    assert cyberagent._handle_logs(args) == 0
    output = capsys.readouterr().out
    assert "Invalid log level" not in output
    assert "ERROR" in output
    assert "INFO" not in output


def test_handle_logs_invalid_level_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "runtime_20250101_000000.log"
    log_file.write_text("2025-01-01 00:00:00.000 INFO [x] ok\n", encoding="utf-8")

    monkeypatch.setattr(cyberagent, "LOGS_DIR", log_dir)

    args = argparse.Namespace(
        filter=None,
        level=["bad"],
        follow=False,
        limit=200,
    )

    assert cyberagent._handle_logs(args) == 2
    output = capsys.readouterr().out
    assert "Invalid log level" in output


def test_check_recent_runtime_errors_counts_new(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "runtime_20250101_000000.log"
    log_file.write_text(
        "\n".join(
            [
                "2025-01-01 00:00:00.000 INFO [x] ok",
                "2025-01-01 00:00:01.000 WARNING [x] warn",
                "2025-01-01 00:00:02.000 ERROR [x] boom",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    state_file = log_dir / "cli_last_seen.json"
    monkeypatch.setattr(cyberagent, "LOGS_DIR", log_dir)
    monkeypatch.setattr(cyberagent, "CLI_LOG_STATE_FILE", state_file)

    cyberagent._check_recent_runtime_errors("status")
    output = capsys.readouterr().out
    assert "1 errors, 1 warnings" in output
    assert "cyberagent logs" in output

    # Second call should be quiet when no new lines exist.
    cyberagent._check_recent_runtime_errors("status")
    output = capsys.readouterr().out
    assert output == ""


def test_check_recent_runtime_errors_resets_on_new_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    now = time.time()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    first_log = log_dir / "runtime_20250101_000000.log"
    first_log.write_text("2025-01-01 00:00:00.000 INFO [x] ok\n", encoding="utf-8")
    os.utime(first_log, (now, now))

    state_file = log_dir / "cli_last_seen.json"
    monkeypatch.setattr(cyberagent, "LOGS_DIR", log_dir)
    monkeypatch.setattr(cyberagent, "CLI_LOG_STATE_FILE", state_file)

    cyberagent._check_recent_runtime_errors("status")
    capsys.readouterr()

    second_log = log_dir / "runtime_20250101_010000.log"
    second_log.write_text(
        "2025-01-01 01:00:00.000 WARNING [x] warn\n", encoding="utf-8"
    )
    os.utime(second_log, (now + 10, now + 10))

    cyberagent._check_recent_runtime_errors("status")
    output = capsys.readouterr().out
    assert "0 errors, 1 warnings" in output
    assert "cyberagent logs" in output


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

    def fake_get_db() -> Iterator[DummySession]:
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
        "onboarding",
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
        [sys.executable, "-m", "src.cyberagent.cli.cyberagent", "start"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=5,
    )
    assert result.returncode == 0
    assert "Runtime start stubbed" in result.stdout
    assert "cyberagent suggest" in result.stdout


def test_start_spawns_serve_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded: dict[str, object] = {}

    class DummyProcess:
        def __init__(
            self,
            cmd: Sequence[str],
            *,
            env: dict[str, str],
            stdout,
            stderr,
            close_fds: bool,
        ):
            recorded["cmd"] = cmd
            recorded["env"] = env
            self.pid = 4242

    monkeypatch.setenv("CYBERAGENT_TEST_NO_RUNTIME", "")
    monkeypatch.setattr(subprocess, "Popen", DummyProcess)
    monkeypatch.setattr(cyberagent, "get_last_team_id", lambda: 7)
    monkeypatch.setattr(cyberagent, "init_db", lambda: None)
    target_pid = tmp_path / "serve.pid"
    monkeypatch.setattr(cyberagent, "RUNTIME_PID_FILE", target_pid)
    exit_code = cyberagent.main(["start"])
    assert exit_code == 0
    recorded_cmd = cast(Sequence[str], recorded["cmd"])
    assert recorded_cmd[0] == sys.executable
    assert recorded_cmd[3] == cyberagent.SERVE_COMMAND
    recorded_env = cast(dict[str, str], recorded["env"])
    assert recorded_env["CYBERAGENT_ACTIVE_TEAM_ID"] == "7"
    assert target_pid.read_text(encoding="utf-8") == "4242"


def test_start_suggests_onboarding_when_no_team(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class DummyProcess:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("Runtime should not start without a team.")

    monkeypatch.setenv("CYBERAGENT_TEST_NO_RUNTIME", "")
    monkeypatch.setattr(subprocess, "Popen", DummyProcess)
    monkeypatch.setattr(cyberagent, "get_last_team_id", lambda: None)
    monkeypatch.setattr(cyberagent, "init_db", lambda: None)

    exit_code = cyberagent.main(["start"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "cyberagent onboarding" in output


@pytest.mark.asyncio
async def test_send_suggestion_sets_user_sender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class DummyRuntime:
        async def send_message(
            self, message, recipient, sender=None, **kwargs
        ):  # noqa: ANN001
            captured["sender"] = sender

    async def fake_register() -> None:
        return None

    async def fake_stop() -> None:
        return None

    monkeypatch.setattr(cyberagent, "get_runtime", lambda: DummyRuntime())
    monkeypatch.setattr(cyberagent, "register_systems", fake_register)
    monkeypatch.setattr(cyberagent, "stop_runtime", fake_stop)
    monkeypatch.setattr(cyberagent, "init_db", lambda: None)

    parsed = cyberagent.ParsedSuggestion(payload_text="hi", payload_object="hi")
    await cyberagent._send_suggestion(parsed)

    assert captured["sender"] == AgentId(type="UserAgent", key="root")


@pytest.mark.asyncio
async def test_send_suggestion_prints_inbox_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stopped: dict[str, bool] = {"value": False}

    class DummyRuntime:
        async def send_message(
            self, message, recipient, sender=None, **kwargs
        ):  # noqa: ANN001
            return None

    async def fake_register() -> None:
        return None

    async def fake_stop() -> None:
        stopped["value"] = True

    monkeypatch.setattr(cyberagent, "get_runtime", lambda: DummyRuntime())
    monkeypatch.setattr(cyberagent, "register_systems", fake_register)
    monkeypatch.setattr(cyberagent, "stop_runtime", fake_stop)
    monkeypatch.setattr(cyberagent, "init_db", lambda: None)

    parsed = cyberagent.ParsedSuggestion(payload_text="hi", payload_object="hi")
    await cyberagent._send_suggestion(parsed)

    output = capsys.readouterr().out
    assert "Suggestion delivered to System4." in output
    assert "cyberagent inbox" in output
    assert "cyberagent watch" in output
    assert stopped["value"] is True


@pytest.mark.asyncio
async def test_send_suggestion_shutdown_timeout_exits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class DummyRuntime:
        async def send_message(
            self, message, recipient, sender=None, **kwargs
        ):  # noqa: ANN001
            return None

    async def fake_register() -> None:
        return None

    async def slow_stop() -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(cyberagent, "get_runtime", lambda: DummyRuntime())
    monkeypatch.setattr(cyberagent, "register_systems", fake_register)
    monkeypatch.setattr(cyberagent, "stop_runtime", slow_stop)
    monkeypatch.setattr(cyberagent, "init_db", lambda: None)
    monkeypatch.setattr(cyberagent, "SUGGEST_SHUTDOWN_TIMEOUT_SECONDS", 0.01)

    parsed = cyberagent.ParsedSuggestion(payload_text="hi", payload_object="hi")
    await asyncio.wait_for(cyberagent._send_suggestion(parsed), timeout=0.2)

    output = capsys.readouterr().out
    assert "Runtime shutdown timed out" in output


@pytest.mark.asyncio
async def test_send_suggestion_send_timeout_exits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class DummyRuntime:
        async def send_message(
            self, message, recipient, sender=None, **kwargs
        ):  # noqa: ANN001
            await asyncio.Event().wait()

    async def fake_register() -> None:
        return None

    async def fake_stop() -> None:
        return None

    monkeypatch.setattr(cyberagent, "get_runtime", lambda: DummyRuntime())
    monkeypatch.setattr(cyberagent, "register_systems", fake_register)
    monkeypatch.setattr(cyberagent, "stop_runtime", fake_stop)
    monkeypatch.setattr(cyberagent, "init_db", lambda: None)
    monkeypatch.setattr(cyberagent, "SUGGEST_SEND_TIMEOUT_SECONDS", 0.01)

    parsed = cyberagent.ParsedSuggestion(payload_text="hi", payload_object="hi")
    await asyncio.wait_for(cyberagent._send_suggestion(parsed), timeout=0.2)

    output = capsys.readouterr().out
    assert "Suggestion send timed out" in output


@pytest.mark.asyncio
async def test_send_suggestion_handles_output_parse_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stopped: dict[str, bool] = {"value": False}

    class DummyError(Exception):
        def __init__(self) -> None:
            super().__init__("output_parse_failed")
            self.code = "output_parse_failed"

    class DummyRuntime:
        async def send_message(
            self, message, recipient, sender=None, **kwargs
        ):  # noqa: ANN001
            raise DummyError()

    async def fake_register() -> None:
        return None

    async def fake_stop() -> None:
        stopped["value"] = True

    monkeypatch.setattr(cyberagent, "get_runtime", lambda: DummyRuntime())
    monkeypatch.setattr(cyberagent, "register_systems", fake_register)
    monkeypatch.setattr(cyberagent, "stop_runtime", fake_stop)
    monkeypatch.setattr(cyberagent, "init_db", lambda: None)

    parsed = cyberagent.ParsedSuggestion(payload_text="hi", payload_object="hi")
    await cyberagent._send_suggestion(parsed)

    output = capsys.readouterr().out
    assert "could not be parsed" in output
    assert stopped["value"] is True


@pytest.mark.asyncio
async def test_send_suggestion_timeout_does_not_cancel_runtime_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.cancelled = False
            self.task: asyncio.Task[None] | None = None

        async def send_message(self, **kwargs: object) -> None:
            async def _run() -> None:
                await asyncio.sleep(0.05)

            self.task = asyncio.create_task(_run())
            try:
                await self.task
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    async def fake_register_systems() -> None:
        return None

    async def fake_stop_runtime_with_timeout() -> None:
        return None

    runtime = DummyRuntime()
    monkeypatch.setattr(cyberagent, "init_db", lambda: None)
    monkeypatch.setattr(cyberagent, "register_systems", fake_register_systems)
    monkeypatch.setattr(cyberagent, "get_runtime", lambda: runtime)
    monkeypatch.setattr(
        cyberagent, "_stop_runtime_with_timeout", fake_stop_runtime_with_timeout
    )
    monkeypatch.setattr(cyberagent, "SUGGEST_SEND_TIMEOUT_SECONDS", 0.01)

    parsed = cyberagent.ParsedSuggestion(
        payload_text="Run a full tool test",
        payload_object="Run a full tool test",
    )

    await cyberagent._send_suggestion(parsed)
    assert runtime.task is not None
    await runtime.task
    assert runtime.cancelled is False


def test_loads_op_service_account_token_from_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "OP_SERVICE_ACCOUNT_TOKEN=service-token\n", encoding="utf-8"
    )

    load_op_service_account_token()

    assert os.environ.get("OP_SERVICE_ACCOUNT_TOKEN") == "service-token"


def test_loads_op_service_account_token_from_parent_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    root = tmp_path / "repo"
    nested = root / "subdir"
    nested.mkdir(parents=True)
    (root / ".env").write_text(
        "OP_SERVICE_ACCOUNT_TOKEN=service-token\n", encoding="utf-8"
    )
    monkeypatch.chdir(nested)

    load_op_service_account_token()

    assert os.environ.get("OP_SERVICE_ACCOUNT_TOKEN") == "service-token"


@pytest.mark.asyncio
async def test_dev_system_run_sends_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def send_message(self, **kwargs: object) -> None:
            self.calls.append(kwargs)

    async def fake_register_systems() -> None:
        return None

    async def fake_stop_runtime_with_timeout() -> None:
        return None

    runtime = DummyRuntime()
    monkeypatch.setattr(cyberagent, "init_db", lambda: None)
    monkeypatch.setattr(cyberagent, "register_systems", fake_register_systems)
    monkeypatch.setattr(cyberagent, "get_runtime", lambda: runtime)
    monkeypatch.setattr(
        cyberagent, "_stop_runtime_with_timeout", fake_stop_runtime_with_timeout
    )
    monkeypatch.setattr(cyberagent, "SUGGEST_SEND_TIMEOUT_SECONDS", 0.5)

    args = argparse.Namespace(
        dev_command="system-run",
        system_id="System4/root",
        message="Ping",
    )

    exit_code = await cyberagent._handle_dev(args)
    assert exit_code == 0
    assert runtime.calls
    assert runtime.calls[0]["recipient"] == AgentId.from_str("System4/root")
