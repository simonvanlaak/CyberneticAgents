from __future__ import annotations

from src.cyberagent.cli import cyberagent


def test_build_parser_includes_kanban_command() -> None:
    parser = cyberagent.build_parser()

    args = parser.parse_args(["kanban"])

    assert args.command == "kanban"


def test_kanban_command_prints_planka_ui_url(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("PLANKA_BASE_URL", "http://planka.local:3000")

    exit_code = cyberagent.main(["kanban"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Planka" in output
    assert "http://planka.local:3000" in output


def test_kanban_command_uses_planka_base_url_default(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.delenv("PLANKA_BASE_URL", raising=False)
    monkeypatch.setenv("PLANKA_PUBLIC_PORT", "3000")

    exit_code = cyberagent.main(["kanban"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Planka" in output
    assert "3000" in output


def test_kanban_command_does_not_reference_taiga(
    monkeypatch,
    capsys,
) -> None:
    """Regression: kanban output must not reference Taiga after migration."""
    monkeypatch.setenv("PLANKA_BASE_URL", "http://planka.local:3000")

    cyberagent.main(["kanban"])

    output = capsys.readouterr().out
    assert "Taiga" not in output
    assert "taiga" not in output
