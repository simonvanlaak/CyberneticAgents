from __future__ import annotations

from src.cyberagent.cli import cyberagent


def test_build_parser_includes_kanban_command() -> None:
    parser = cyberagent.build_parser()

    args = parser.parse_args(["kanban"])

    assert args.command == "kanban"


def test_kanban_command_prints_taiga_ui_url(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("TAIGA_BASE_URL", "http://taiga.local:9000")

    exit_code = cyberagent.main(["kanban"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Taiga UI" in output
    assert "http://taiga.local:9000" in output
