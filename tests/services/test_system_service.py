def test_get_system_delegates(monkeypatch):
    from src.cyberagent.services import systems as system_service

    monkeypatch.setattr(system_service, "_get_system", lambda system_id: "sys")

    assert system_service.get_system(5) == "sys"


def test_get_system_by_type_delegates(monkeypatch):
    from src.cyberagent.services import systems as system_service
    from src.enums import SystemType

    monkeypatch.setattr(
        system_service,
        "_get_system_by_type",
        lambda team_id, system_type: "typed",
    )

    assert system_service.get_system_by_type(1, SystemType.CONTROL) == "typed"


def test_get_systems_by_type_delegates(monkeypatch):
    from src.cyberagent.services import systems as system_service
    from src.enums import SystemType

    monkeypatch.setattr(
        system_service,
        "_get_systems_by_type",
        lambda team_id, system_type: ["s1"],
    )

    assert system_service.get_systems_by_type(1, SystemType.CONTROL) == ["s1"]


def test_ensure_default_systems_for_team_delegates(monkeypatch):
    from src.cyberagent.services import systems as system_service

    monkeypatch.setattr(
        system_service,
        "_ensure_default_systems_for_team",
        lambda team_id: ["default"],
    )

    assert system_service.ensure_default_systems_for_team(1) == ["default"]
