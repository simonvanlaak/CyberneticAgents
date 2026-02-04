from __future__ import annotations

from pathlib import Path

import pytest

from src.cyberagent.cli import cyberagent


def test_reset_removes_data_and_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    logs_dir = tmp_path / "logs"
    data_dir.mkdir()
    logs_dir.mkdir()
    (data_dir / ".gitkeep").write_text("", encoding="utf-8")
    (data_dir / "CyberneticAgents.db").write_text("db", encoding="utf-8")
    (logs_dir / "runtime.log").write_text("log", encoding="utf-8")

    exit_code = cyberagent.main(["reset", "--yes"])

    assert exit_code == 0
    assert data_dir.exists()
    assert (data_dir / ".gitkeep").exists()
    assert not (data_dir / "CyberneticAgents.db").exists()
    assert not logs_dir.exists()


def test_reset_preserves_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text("KEY=value\n", encoding="utf-8")
    (tmp_path / "data").mkdir()

    exit_code = cyberagent.main(["reset", "--yes"])

    assert exit_code == 0
    assert env_file.exists()
