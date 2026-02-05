"""Message routing services (rules + dead-letter queue)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.dead_letter_message import DeadLetterMessage
from src.cyberagent.db.models.routing_rule import RoutingRule
from src.cyberagent.services import recursions as recursions_service
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services.audit import log_event
from src.enums import SystemType


@dataclass(frozen=True)
class RoutingContext:
    channel: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class RoutingDecision:
    targets: list[str]
    dlq_entry_id: int | None
    dlq_reason: str | None


def create_routing_rule(
    *,
    team_id: int,
    name: str,
    channel: str,
    filters: dict[str, str] | None,
    targets: list[dict[str, Any]],
    priority: int = 0,
    active: bool = True,
    created_by_system_id: int | None = None,
) -> RoutingRule:
    """
    Create and persist a routing rule.
    """
    now = datetime.utcnow()
    rule = RoutingRule(
        team_id=team_id,
        name=name,
        channel=channel,
        filters_json=json.dumps(filters or {}),
        targets_json=json.dumps(targets),
        priority=priority,
        active=active,
        created_by_system_id=created_by_system_id,
        updated_by_system_id=created_by_system_id,
        created_at=now,
        updated_at=now,
    )
    session = next(get_db())
    try:
        session.add(rule)
        session.commit()
        session.refresh(rule)
        return rule
    finally:
        session.close()


def list_routing_rules(team_id: int, *, active_only: bool = True) -> list[RoutingRule]:
    session = next(get_db())
    try:
        query = session.query(RoutingRule).filter(RoutingRule.team_id == team_id)
        if active_only:
            query = query.filter(RoutingRule.active.is_(True))
        return list(query.order_by(RoutingRule.priority.desc(), RoutingRule.id.asc()))
    finally:
        session.close()


def match_routing_rules(
    *, team_id: int, channel: str, metadata: dict[str, str]
) -> list[RoutingRule]:
    """
    Return routing rules that match the provided channel + metadata (exact match).
    """
    context = RoutingContext(channel=channel, metadata=metadata)
    candidates = list_routing_rules(team_id)
    return [rule for rule in candidates if _rule_matches(rule, context)]


def resolve_message_decision(
    *, team_id: int, channel: str, metadata: dict[str, str]
) -> RoutingDecision:
    """
    Resolve final target agent ids for a message, recursing into subteams.

    Returns:
        List of agent_id_str values.
    """
    context = RoutingContext(channel=channel, metadata=metadata)
    matched = match_routing_rules(team_id=team_id, channel=channel, metadata=metadata)
    if not matched:
        targets, dlq_id, reason = _record_dlq_and_default(
            team_id, context, reason="no_route"
        )
        return RoutingDecision(targets=targets, dlq_entry_id=dlq_id, dlq_reason=reason)

    targets: list[str] = []
    for rule in matched:
        rule_targets: list[str] = []
        for target in rule.targets():
            rule_targets.extend(_resolve_target(team_id, context, target))
        if rule_targets:
            log_event(
                "routing_match",
                service="routing",
                team_id=team_id,
                rule_id=rule.id,
                channel=context.channel,
                target_count=len(rule_targets),
            )
        targets.extend(rule_targets)
    if not targets:
        targets, dlq_id, reason = _record_dlq_and_default(
            team_id, context, reason="no_target"
        )
        return RoutingDecision(targets=targets, dlq_entry_id=dlq_id, dlq_reason=reason)
    return RoutingDecision(targets=targets, dlq_entry_id=None, dlq_reason=None)


def resolve_message_targets(
    *, team_id: int, channel: str, metadata: dict[str, str]
) -> list[str]:
    return resolve_message_decision(
        team_id=team_id,
        channel=channel,
        metadata=metadata,
    ).targets


def list_dead_letters(
    *, team_id: int, status: str | None = None
) -> list[DeadLetterMessage]:
    session = next(get_db())
    try:
        query = session.query(DeadLetterMessage).filter(
            DeadLetterMessage.team_id == team_id
        )
        if status is not None:
            query = query.filter(DeadLetterMessage.status == status)
        return list(query.order_by(DeadLetterMessage.id.asc()))
    finally:
        session.close()


def _rule_matches(rule: RoutingRule, context: RoutingContext) -> bool:
    if not rule.active:
        return False
    if rule.channel != "*" and rule.channel != context.channel:
        return False
    filters = rule.filters()
    for key, value in filters.items():
        if key == "channel":
            if str(value) != context.channel:
                return False
            continue
        if str(context.metadata.get(key)) != str(value):
            return False
    return True


def _resolve_target(
    team_id: int, context: RoutingContext, target: dict[str, Any]
) -> list[str]:
    if "system_id" in target:
        return _resolve_system_target(target["system_id"])
    if "team_id" in target:
        return _resolve_team_target(team_id, context, target["team_id"])
    return []


def _resolve_system_target(system_id_value: Any) -> list[str]:
    system = None
    if isinstance(system_id_value, int):
        system = systems_service.get_system(system_id_value)
    elif isinstance(system_id_value, str):
        system = systems_service.get_system_by_agent_id(system_id_value)
    if system is None:
        return []
    return [_normalize_agent_id_str(system)]


def _normalize_agent_id_str(system: Any) -> str:
    agent_id_str = system.agent_id_str
    if "/" in agent_id_str:
        return agent_id_str
    fallback_name = getattr(system, "name", "")
    if isinstance(fallback_name, str) and "/" in fallback_name:
        return fallback_name
    system_type = getattr(system, "type", None)
    if system_type == SystemType.OPERATION:
        agent_type = "System1"
    elif system_type == SystemType.CONTROL:
        agent_type = "System3"
    elif system_type == SystemType.INTELLIGENCE:
        agent_type = "System4"
    elif system_type == SystemType.POLICY:
        agent_type = "System5"
    else:
        agent_type = "System1"
    return f"{agent_type}/root"


def _resolve_team_target(
    current_team_id: int, context: RoutingContext, team_id_value: Any
) -> list[str]:
    if not isinstance(team_id_value, int):
        return []
    recursion = recursions_service.get_recursion(team_id_value)
    if recursion is None or recursion.parent_team_id != current_team_id:
        return []
    return resolve_message_targets(
        team_id=team_id_value, channel=context.channel, metadata=context.metadata
    )


def _record_dlq_and_default(
    team_id: int, context: RoutingContext, reason: str
) -> tuple[list[str], int | None, str]:
    dlq_id = _record_dead_letter(team_id=team_id, context=context, reason=reason)
    log_event(
        "routing_dlq",
        service="routing",
        team_id=team_id,
        channel=context.channel,
        reason=reason,
        dlq_id=dlq_id,
    )
    system4 = systems_service.get_system_by_type(team_id, SystemType.INTELLIGENCE)
    if system4 is None:
        return [], dlq_id, reason
    return [system4.agent_id_str], dlq_id, reason


def _record_dead_letter(
    *, team_id: int, context: RoutingContext, reason: str
) -> int | None:
    payload = {
        "channel": context.channel,
        "metadata": context.metadata,
    }
    dlq = DeadLetterMessage(
        team_id=team_id,
        channel=context.channel,
        payload_json=json.dumps(payload),
        reason=reason,
        status="pending",
        received_at=datetime.utcnow(),
        handled_by_system_id=None,
    )
    session = next(get_db())
    try:
        session.add(dlq)
        session.commit()
        session.refresh(dlq)
        return dlq.id
    finally:
        session.close()
