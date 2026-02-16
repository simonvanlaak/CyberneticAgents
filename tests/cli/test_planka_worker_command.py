from __future__ import annotations

import argparse

from src.cyberagent.cli import cyberagent


def test_parser_includes_planka_worker_command() -> None:
    parser = cyberagent.build_parser()
    args = parser.parse_args(["planka", "worker", "--once", "--max-cards", "2"])

    assert args.command == "planka"
    assert args.planka_command == "worker"
    assert args.once is True
    assert args.max_cards == 2


def test_main_dispatches_planka_command(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_handle_planka(args: argparse.Namespace) -> int:
        captured["command"] = args.command
        captured["planka_command"] = args.planka_command
        return 0

    monkeypatch.setattr(cyberagent, "_handle_planka", _fake_handle_planka)
    monkeypatch.setitem(cyberagent._HANDLERS, "planka", _fake_handle_planka)

    exit_code = cyberagent.main(["planka", "worker", "--once"])

    assert exit_code == 0
    assert captured == {"command": "planka", "planka_command": "worker"}
