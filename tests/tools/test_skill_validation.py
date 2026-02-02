from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.cyberagent.tools.cli_executor import skill_validation


def test_validate_skills_runs_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: dict[str, list[str]] = {}

    def _run(cmd, check, capture_output, text):
        calls["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(skill_validation.subprocess, "run", _run)

    skill_validation.validate_skills(tmp_path)

    assert calls["cmd"][0] == "skills-ref"
    assert calls["cmd"][1] == "validate"
    assert calls["cmd"][2] == str(tmp_path)


def test_validate_skills_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run(*_args, **_kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(skill_validation.subprocess, "run", _run)

    with pytest.raises(RuntimeError, match="skills-ref"):
        skill_validation.validate_skills(Path("skills"))


def test_validate_skills_reports_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run(*_args, **_kwargs):
        return SimpleNamespace(returncode=2, stdout="bad", stderr="err")

    monkeypatch.setattr(skill_validation.subprocess, "run", _run)

    with pytest.raises(RuntimeError, match="skills-ref"):
        skill_validation.validate_skills(Path("skills"))
