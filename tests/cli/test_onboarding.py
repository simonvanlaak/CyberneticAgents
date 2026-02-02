from __future__ import annotations

import argparse

import pytest

from src.cyberagent.cli import cyberagent
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team

ONBOARDING = getattr(cyberagent, "onboarding_cli", cyberagent)


def _handle_onboarding(args: argparse.Namespace) -> int:
    if hasattr(ONBOARDING, "handle_onboarding"):
        return ONBOARDING.handle_onboarding(args, cyberagent.SUGGEST_COMMAND)
    return ONBOARDING._handle_onboarding(args)


def _patch_run_checks(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    attr = (
        "run_technical_onboarding_checks"
        if hasattr(ONBOARDING, "run_technical_onboarding_checks")
        else "_run_technical_onboarding_checks"
    )
    monkeypatch.setattr(ONBOARDING, attr, lambda: value)


def _clear_teams() -> None:
    session = next(get_db())
    try:
        session.query(System).delete()
        session.query(Team).delete()
        session.commit()
    finally:
        session.close()


def test_handle_onboarding_creates_default_team(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()
    _patch_run_checks(monkeypatch, True)

    exit_code = _handle_onboarding(argparse.Namespace())
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "Created default team" in captured
    assert "cyberagent suggest" in captured

    expected_name = (
        "root" if hasattr(ONBOARDING, "handle_onboarding") else "default_team"
    )
    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == expected_name).first()
        assert team is not None
    finally:
        session.close()


def test_handle_onboarding_skips_when_team_exists(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()
    session = next(get_db())
    try:
        session.add(Team(name="existing_team"))
        session.commit()
    finally:
        session.close()

    _patch_run_checks(monkeypatch, True)

    exit_code = _handle_onboarding(argparse.Namespace())
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "Team already exists" in captured
    assert "cyberagent suggest" in captured

    session = next(get_db())
    try:
        assert session.query(Team).count() == 1
    finally:
        session.close()


def test_handle_onboarding_requires_technical_checks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()

    _patch_run_checks(monkeypatch, False)

    exit_code = _handle_onboarding(argparse.Namespace())
    captured = capsys.readouterr().out

    assert exit_code == 1
    assert "technical onboarding" in captured.lower()
