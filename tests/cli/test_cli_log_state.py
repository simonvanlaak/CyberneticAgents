from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.cli import cyberagent


def test_build_parser_accepts_status_command() -> None:
    parser = cyberagent.build_parser()

    args = parser.parse_args(["status"])

    assert args.command == "status"


def test_check_recent_runtime_errors_skips_logs_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "runtime_20250101_000000.log"
    log_file.write_text(
        "2025-01-01 00:00:00.000 WARNING [x] warn\n",
        encoding="utf-8",
    )
    state_file = log_dir / "cli_last_seen.json"
    monkeypatch.setattr(cyberagent, "LOGS_DIR", log_dir)
    monkeypatch.setattr(cyberagent, "CLI_LOG_STATE_FILE", state_file)

    cyberagent._check_recent_runtime_errors("logs")

    output = capsys.readouterr().out
    assert output == ""
    assert state_file.exists() is False
