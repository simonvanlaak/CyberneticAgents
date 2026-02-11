from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from src.cyberagent.cli import cyberagent


def test_handle_logs_reads_all_session_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "cyberagent.pid").touch()

    first_log = log_dir / "runtime_20250101_000000.log"
    second_log = log_dir / "runtime_20250101_000001.log"
    first_log.write_text("2025-01-01 00:00:01.000 ERROR [x] first\n", encoding="utf-8")
    second_log.write_text(
        "2025-01-01 00:00:02.000 ERROR [x] second\n", encoding="utf-8"
    )
    first_log.touch()
    second_log.touch()

    monkeypatch.setattr(cyberagent, "LOGS_DIR", log_dir)
    args = argparse.Namespace(filter=None, level=None, follow=False, limit=200)

    assert cyberagent._handle_logs(args) == 0
    output = capsys.readouterr().out
    assert "first" in output
    assert "second" in output


def test_handle_logs_default_shows_all_session_errors_without_truncation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "cyberagent.pid").touch()
    log_file = log_dir / "runtime_20250101_000000.log"
    lines = [f"2025-01-01 00:00:{i:02d}.000 ERROR [x] err-{i}" for i in range(250)]
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log_file.touch()

    monkeypatch.setattr(cyberagent, "LOGS_DIR", log_dir)
    args = argparse.Namespace(filter=None, level=None, follow=False, limit=200)

    assert cyberagent._handle_logs(args) == 0
    output_lines = [
        line for line in capsys.readouterr().out.splitlines() if "ERROR" in line
    ]
    assert len(output_lines) == 250
