from __future__ import annotations

from pathlib import Path

from src.cyberagent.core import paths


def test_get_data_dir_uses_cyberagent_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CYBERAGENT_ROOT", str(tmp_path))

    assert paths.get_data_dir() == tmp_path / "data"


def test_get_logs_dir_uses_cyberagent_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CYBERAGENT_ROOT", str(tmp_path))

    assert paths.get_logs_dir() == tmp_path / "logs"


def test_get_repo_root_falls_back_to_module_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CYBERAGENT_ROOT", raising=False)
    monkeypatch.setattr(paths, "_repo_root_from_module", lambda: tmp_path)

    assert paths.get_repo_root() == tmp_path
