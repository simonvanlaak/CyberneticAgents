"""Recursion linkage services for VSM sub-teams."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.recursion import Recursion
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team


@dataclass(frozen=True)
class RecursionLink:
    sub_team_id: int
    origin_system_id: int
    parent_team_id: int


def create_recursion(
    sub_team_id: int,
    origin_system_id: int,
    parent_team_id: int,
    actor_id: str,
) -> Recursion:
    """
    Create a recursion linkage record.

    Args:
        sub_team_id: The newly created sub-team id.
        origin_system_id: The System1 id in the parent team.
        parent_team_id: The parent team id.
        actor_id: Actor performing the mutation (audit only).

    Raises:
        ValueError: If linkage already exists or ids are invalid.
    """
    session = next(get_db())
    try:
        if (
            session.query(Recursion)
            .filter(Recursion.sub_team_id == sub_team_id)
            .first()
        ):
            raise ValueError(f"Recursion already exists for sub_team_id {sub_team_id}.")

        parent_team = session.query(Team).filter(Team.id == parent_team_id).first()
        if parent_team is None:
            raise ValueError(f"Parent team id {parent_team_id} is not registered.")

        sub_team = session.query(Team).filter(Team.id == sub_team_id).first()
        if sub_team is None:
            raise ValueError(f"Sub team id {sub_team_id} is not registered.")

        origin_system = (
            session.query(System).filter(System.id == origin_system_id).first()
        )
        if origin_system is None:
            raise ValueError(f"Origin system id {origin_system_id} is not registered.")
        if origin_system.team_id != parent_team_id:
            raise ValueError(
                f"Origin system {origin_system_id} does not belong to team {parent_team_id}."
            )

        recursion = Recursion(
            sub_team_id=sub_team_id,
            origin_system_id=origin_system_id,
            parent_team_id=parent_team_id,
            created_at=datetime.utcnow(),
            created_by=actor_id,
        )
        session.add(recursion)
        session.commit()
        return recursion
    finally:
        session.close()


def get_recursion(sub_team_id: int) -> Recursion | None:
    """
    Return the recursion linkage for a sub-team.
    """
    session = next(get_db())
    try:
        return (
            session.query(Recursion)
            .filter(Recursion.sub_team_id == sub_team_id)
            .first()
        )
    finally:
        session.close()


def get_recursion_chain(team_id: int) -> list[RecursionLink]:
    """
    Walk up recursion links for the given team id.

    Returns:
        Ordered list of recursion links from the provided team upwards.
    """
    links: list[RecursionLink] = []
    visited: set[int] = set()
    current_team_id = team_id

    while current_team_id not in visited:
        visited.add(current_team_id)
        link = get_recursion(current_team_id)
        if link is None:
            break
        links.append(
            RecursionLink(
                sub_team_id=link.sub_team_id,
                origin_system_id=link.origin_system_id,
                parent_team_id=link.parent_team_id,
            )
        )
        current_team_id = link.parent_team_id

    return links
