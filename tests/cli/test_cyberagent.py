from __future__ import annotations

from typing import Sequence

import pytest

from src.cli import cyberagent


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
