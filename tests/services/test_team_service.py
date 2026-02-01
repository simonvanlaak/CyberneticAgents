import pytest


def test_get_team_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import teams as team_service

    monkeypatch.setattr(team_service, "_get_team", lambda team_id: "team")

    assert team_service.get_team(1) == "team"
