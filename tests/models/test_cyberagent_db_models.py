import importlib


def test_models_shims_point_to_new_locations() -> None:
    old_system = importlib.import_module("src.models.system")
    new_system = importlib.import_module("src.cyberagent.db.models.system")
    assert old_system.System is new_system.System

    old_team = importlib.import_module("src.models.team")
    new_team = importlib.import_module("src.cyberagent.db.models.team")
    assert old_team.Team is new_team.Team

    old_policy = importlib.import_module("src.models.policy")
    new_policy = importlib.import_module("src.cyberagent.db.models.policy")
    assert old_policy.Policy is new_policy.Policy


def test_domain_serialization_shim() -> None:
    old_serialize = importlib.import_module("src.models.serialize")
    new_serialize = importlib.import_module("src.cyberagent.domain.serialize")

    assert old_serialize.model_to_dict is new_serialize.model_to_dict


def test_system_default_specs_available() -> None:
    domain_specs = importlib.import_module("src.cyberagent.domain.system_specs")
    assert len(domain_specs.DEFAULT_SYSTEM_SPECS) >= 4
