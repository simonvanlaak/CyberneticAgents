"""Typed message construction helpers for orchestration flows."""

from __future__ import annotations

from src.agents.messages import InitiativeAssignMessage


def build_initiative_assign_message(initiative_id: int) -> InitiativeAssignMessage:
    """Build a normalized initiative assignment message."""
    source = f"initiative_{initiative_id}"
    return InitiativeAssignMessage(
        initiative_id=initiative_id,
        source=source,
        content=f"Start initiative {initiative_id}.",
    )
