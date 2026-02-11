import json
from pathlib import Path


def test_root_team_defaults_grant_obsidian_skills_to_system1() -> None:
    """Regression: System1 must be able to load full PKM docs via Obsidian skills.

    We enforce this at the default team config level:
    - Skills must be allowed at the team envelope (allowed_skills)
    - System1/root must be granted the skills (skill_grants)
    """

    config_path = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "defaults"
        / "teams"
        / "root_team.json"
    )
    data = json.loads(config_path.read_text(encoding="utf-8"))

    allowed = set(data.get("allowed_skills") or [])
    assert "obsidian-search" in allowed
    assert "obsidian-get" in allowed
    assert "task_search" in allowed

    systems = data.get("systems") or []
    system1 = next((s for s in systems if s.get("agent_id") == "System1/root"), None)
    assert system1 is not None

    grants = set(system1.get("skill_grants") or [])
    assert "obsidian-search" in grants
    assert "obsidian-get" in grants
    assert "task_search" in grants
