from typing import cast

import pytest


class _FakeInitiative:
    def __init__(self) -> None:
        self.status = None
        self.updated = False
        self.name = None
        self.description = None

    def set_status(self, status) -> None:
        self.status = status

    def update(self) -> None:
        self.updated = True

    def add(self) -> int:
        self.updated = True
        return 7


def test_start_initiative_updates_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import initiatives as initiative_service

    initiative = _FakeInitiative()
    monkeypatch.setattr(
        initiative_service, "_get_initiative", lambda initiative_id: initiative
    )

    result = initiative_service.start_initiative(10)

    assert result is initiative
    assert initiative.updated is True
    assert initiative.status is not None


def test_start_initiative_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import initiatives as initiative_service

    monkeypatch.setattr(
        initiative_service, "_get_initiative", lambda initiative_id: None
    )

    with pytest.raises(ValueError):
        initiative_service.start_initiative(42)


def test_create_initiative_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import initiatives as initiative_service

    class _FactoryInitiative(_FakeInitiative):
        def __init__(self, **kwargs) -> None:
            super().__init__()
            self.name = kwargs.get("name")
            self.description = kwargs.get("description")
            self.team_id = kwargs.get("team_id")
            self.strategy_id = kwargs.get("strategy_id")

    monkeypatch.setattr(initiative_service, "Initiative", _FactoryInitiative)

    initiative = initiative_service.create_initiative(1, 2, "Init", "Desc")

    assert isinstance(initiative, _FactoryInitiative)
    assert initiative.name == "Init"
    assert initiative.description == "Desc"
    assert initiative.team_id == 1
    assert initiative.strategy_id == 2


def test_update_initiative_fields() -> None:
    from src.cyberagent.services import initiatives as initiative_service
    from src.cyberagent.db.models.initiative import Initiative

    initiative = cast(Initiative, _FakeInitiative())

    initiative_service.update_initiative_fields(initiative, name="N", description="D")

    assert initiative.name == "N"
    assert initiative.description == "D"
    assert initiative.updated is True


def test_get_initiative_by_id_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import initiatives as initiative_service

    initiative = _FakeInitiative()
    monkeypatch.setattr(
        initiative_service, "_get_initiative", lambda initiative_id: initiative
    )

    assert initiative_service.get_initiative_by_id(5) is initiative


def test_get_initiative_by_id_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cyberagent.services import initiatives as initiative_service

    monkeypatch.setattr(
        initiative_service, "_get_initiative", lambda initiative_id: None
    )

    with pytest.raises(ValueError):
        initiative_service.get_initiative_by_id(9)
