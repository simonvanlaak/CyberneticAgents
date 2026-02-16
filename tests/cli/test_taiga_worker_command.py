from __future__ import annotations

import argparse

from src.cyberagent.cli import cyberagent


def test_parser_includes_taiga_worker_command() -> None:
    parser = cyberagent.build_parser()
    args = parser.parse_args(["taiga", "worker", "--once", "--max-tasks", "3"])

    assert args.command == "taiga"
    assert args.taiga_command == "worker"
    assert args.once is True
    assert args.max_tasks == 3


def test_main_dispatches_taiga_command(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_handle_taiga(args: argparse.Namespace) -> int:
        captured["command"] = args.command
        captured["taiga_command"] = args.taiga_command
        return 0

    monkeypatch.setattr(cyberagent, "_handle_taiga", _fake_handle_taiga)
    monkeypatch.setitem(cyberagent._HANDLERS, "taiga", _fake_handle_taiga)

    exit_code = cyberagent.main(["taiga", "worker", "--once"])

    assert exit_code == 0
    assert captured == {"command": "taiga", "taiga_command": "worker"}
