from __future__ import annotations

from src.cyberagent.services import routing as routing_service


def seed_default_routing_rules(team_id: int, team_defaults: dict[str, object]) -> None:
    rules = team_defaults.get("routing_rules")
    if not isinstance(rules, list):
        return
    existing = {
        rule.name
        for rule in routing_service.list_routing_rules(team_id, active_only=False)
    }
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        name = rule.get("name")
        channel = rule.get("channel")
        targets = rule.get("targets")
        if not isinstance(name, str) or not isinstance(channel, str):
            continue
        if name in existing:
            continue
        if not isinstance(targets, list):
            continue
        filters = rule.get("filters")
        priority = rule.get("priority")
        active = rule.get("active")
        routing_service.create_routing_rule(
            team_id=team_id,
            name=name,
            channel=channel,
            filters=filters if isinstance(filters, dict) else {},
            targets=targets,
            priority=int(priority) if isinstance(priority, int) else 0,
            active=bool(active) if isinstance(active, bool) else True,
            created_by_system_id=None,
        )
