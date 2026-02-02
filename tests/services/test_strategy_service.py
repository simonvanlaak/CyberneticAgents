from typing import cast

import pytest


class _FakeStrategy:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.name = kwargs.get("name")
        self.description = kwargs.get("description")
        self.updated = False

    def add(self) -> int:
        self.updated = True
        return 99

    def update(self) -> None:
        self.updated = True


def test_get_strategy_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import strategies as strategy_service

    monkeypatch.setattr(strategy_service, "_get_strategy", lambda strategy_id: "s")

    assert strategy_service.get_strategy(3) == "s"


def test_get_active_strategy_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import strategies as strategy_service

    monkeypatch.setattr(
        strategy_service, "_get_teams_active_strategy", lambda team_id: "active"
    )

    assert strategy_service.get_teams_active_strategy(1) == "active"


def test_create_strategy_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import strategies as strategy_service

    monkeypatch.setattr(strategy_service, "Strategy", _FakeStrategy)

    strategy = strategy_service.create_strategy(1, 2, "Name", "Desc")

    assert isinstance(strategy, _FakeStrategy)
    assert strategy.kwargs["team_id"] == 1
    assert strategy.kwargs["purpose_id"] == 2
    assert strategy.kwargs["name"] == "Name"
    assert strategy.kwargs["description"] == "Desc"
    assert strategy.kwargs["result"] == ""


def test_update_strategy_fields() -> None:
    from src.cyberagent.services import strategies as strategy_service
    from src.cyberagent.db.models.strategy import Strategy

    strategy = cast(Strategy, _FakeStrategy())

    strategy_service.update_strategy_fields(strategy, name="New", description="D")

    assert strategy.name == "New"
    assert strategy.description == "D"
    assert strategy.updated is True
