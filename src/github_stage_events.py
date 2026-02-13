from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class StageLabelEvent:
    actor_login: str
    label_name: str
    event: str  # "labeled" | "unlabeled"


def _safe_actor_login(raw: dict[str, Any]) -> str:
    actor = raw.get("actor") or {}
    return str(actor.get("login") or "")


def _safe_label_name(raw: dict[str, Any]) -> str:
    label = raw.get("label") or {}
    return str(label.get("name") or "")


def extract_latest_stage_label_event(
    events: Iterable[dict[str, Any]],
) -> Optional[StageLabelEvent]:
    """Return the most recent labeled/unlabeled event for any stage:* label.

    The GitHub Issues events API returns events in ascending order by default.
    We scan and keep the last event that affects a stage:* label.
    """

    latest: Optional[StageLabelEvent] = None
    for e in events:
        event = str(e.get("event") or "")
        if event not in {"labeled", "unlabeled"}:
            continue
        label_name = _safe_label_name(e)
        if not label_name.startswith("stage:"):
            continue
        latest = StageLabelEvent(
            actor_login=_safe_actor_login(e),
            label_name=label_name,
            event=event,
        )
    return latest


def is_stage_ready_set_by_owner(
    events: Iterable[dict[str, Any]],
    *,
    owner_login: str,
    ready_label: str = "stage:ready-to-implement",
) -> bool:
    """Return True if the latest stage:* label event is setting ready_label by owner."""

    latest = extract_latest_stage_label_event(events)
    if latest is None:
        return False
    if latest.event != "labeled":
        return False
    if latest.label_name != ready_label:
        return False
    return latest.actor_login == owner_login
