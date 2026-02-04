from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from src.cyberagent.cli import cyberagent_helpers


def _build_parser_with_topic() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cyberagent")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status")
    return parser


def test_handle_help_prints_root_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cyberagent_helpers.handle_help(_build_parser_with_topic, None)
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "usage:" in captured.out


def test_handle_help_prints_subcommand_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cyberagent_helpers.handle_help(_build_parser_with_topic, "status")
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "status" in captured.out


def test_handle_help_unknown_topic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cyberagent_helpers.handle_help(_build_parser_with_topic, "unknown")
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Unknown help topic" in captured.out


def test_handle_login_uses_keyring(
    capsys: pytest.CaptureFixture[str],
) -> None:
    recorded: dict[str, str] = {}

    class FakeKeyring:
        def set_password(self, service: str, user: str, token: str) -> None:
            recorded["service"] = service
            recorded["user"] = user
            recorded["token"] = token

    exit_code = cyberagent_helpers.handle_login(
        "token-123",
        keyring_available=True,
        keyring_module=FakeKeyring(),
        keyring_service="cyberagent",
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert recorded == {
        "service": "cyberagent",
        "user": "cli",
        "token": "token-123",
    }
    assert "Token stored securely" in captured.out


def test_handle_login_falls_back_to_file(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    exit_code = cyberagent_helpers.handle_login(
        "fallback-token",
        keyring_available=False,
        keyring_module=None,
        keyring_service="cyberagent",
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    token_path = tmp_path / ".cyberagent_token"
    assert token_path.read_text(encoding="utf-8") == "fallback-token"
    assert str(token_path) in captured.out
