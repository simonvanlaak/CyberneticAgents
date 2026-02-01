from types import SimpleNamespace

import pytest

from src.enums import SystemType
from src.cyberagent.db.models import system as system_model


def test_get_system_by_type_single_system(monkeypatch):
    dummy = SimpleNamespace(agent_id_str="System3/root")
    monkeypatch.setattr(
        system_model, "get_systems_by_type", lambda *args, **kwargs: [dummy]
    )

    result = system_model.get_system_by_type(team_id=1, system_type=SystemType.CONTROL)

    assert result is dummy


def test_get_system_by_type_multiple_systems_raises(monkeypatch):
    dummy = SimpleNamespace(agent_id_str="System3/root")
    monkeypatch.setattr(
        system_model, "get_systems_by_type", lambda *args, **kwargs: [dummy, dummy]
    )

    with pytest.raises(ValueError):
        system_model.get_system_by_type(team_id=1, system_type=SystemType.CONTROL)
