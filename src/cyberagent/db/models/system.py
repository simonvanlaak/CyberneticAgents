import json
from typing import List

from autogen_core import AgentId
from sqlalchemy import Enum, ForeignKey, Integer, String, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import Base
from src.cyberagent.domain.serialize import model_to_dict
from src.cyberagent.domain.system_specs import DEFAULT_SYSTEM_SPECS
from src.enums import SystemType


class System(Base):
    __tablename__ = "systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    name: Mapped[int] = mapped_column(String(255), nullable=False)
    type: Mapped[SystemType] = mapped_column(Enum(SystemType), nullable=False)
    agent_id_str: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # AgentId as string

    # Relationships
    team = relationship("Team", back_populates="systems")
    policies = relationship("Policy", back_populates="system")

    def get_agent_id(self) -> AgentId:
        return AgentId.from_str(self.agent_id_str)

    def to_prompt(self) -> List[str]:
        return [json.dumps(model_to_dict(self), indent=4, default=str)]

    def update(self):
        db = next(get_db())
        db.merge(self)
        db.commit()


def ensure_default_systems_for_team(team_id: int) -> List[System]:
    """
    Ensure each team has the default systems registered.

    Args:
        team_id: Team identifier to ensure defaults for.

    Returns:
        A list of newly created System records.
    """
    db = next(get_db())
    created: List[System] = []
    try:
        for system_type, agent_id_str in DEFAULT_SYSTEM_SPECS:
            existing = (
                db.query(System)
                .filter(and_(System.team_id == team_id, System.type == system_type))
                .first()
            )
            if existing:
                continue
            system = System(
                team_id=team_id,
                name=agent_id_str,
                type=system_type,
                agent_id_str=agent_id_str,
            )
            db.add(system)
            created.append(system)
        if created:
            db.commit()
        return created
    finally:
        db.close()


def get_system(system_id: int) -> System:
    """Get system by ID from database"""
    db = next(get_db())
    try:
        return db.query(System).filter(System.id == system_id).first()
    finally:
        db.close()


def get_system_by_type(team_id: int, system_type: int) -> System:
    if system_type == SystemType.OPERATION:
        raise ValueError(
            f"There can be multipel OPERATION Systems in a team. Use {get_systems_by_type.__name__}."
        )
    systems = get_systems_by_type(team_id, system_type)
    if len(systems) > 1:
        raise ValueError(
            f"There are multiple {system_type} systems found in this team. It's supposed to only be one."
        )
    if len(systems) == 0:
        raise ValueError(f"No system found for type {system_type} in team {team_id}.")
    return systems[0]


def get_systems_by_type(team_id: int, system_type: int) -> List[System]:
    db = next(get_db())
    try:
        return (
            db.query(System)
            .filter(and_(System.team_id == team_id, System.type == system_type))
            .all()
        )
    finally:
        db.close()


def get_system_from_agent_id(agent_id_str: str) -> System:
    db = next(get_db())
    try:
        return db.query(System).filter(System.agent_id_str == agent_id_str).first()
    finally:
        db.close()
