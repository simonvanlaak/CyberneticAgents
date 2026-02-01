def test_get_system_policy_prompts_delegates(monkeypatch):
    from src.cyberagent.services import policies as policy_service

    monkeypatch.setattr(
        policy_service, "_get_system_policy_prompts", lambda agent_id: ["p1"]
    )

    assert policy_service.get_system_policy_prompts("agent") == ["p1"]


def test_get_policy_by_id_delegates(monkeypatch):
    from src.cyberagent.services import policies as policy_service

    monkeypatch.setattr(policy_service, "_get_policy", lambda policy_id: "policy")

    assert policy_service.get_policy_by_id(5) == "policy"


def test_get_team_policy_prompts_delegates(monkeypatch):
    from src.cyberagent.services import policies as policy_service

    monkeypatch.setattr(
        policy_service, "_get_team_policy_prompts", lambda agent_id: ["t1"]
    )

    assert policy_service.get_team_policy_prompts("agent") == ["t1"]
