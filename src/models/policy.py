import json
from typing import List

from sqlalchemy import ForeignKey, Integer, String, and_, or_
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db_utils import get_db
from src.init_db import Base
from src.models.serialize import model_to_dict
from src.models.system import get_system_from_agent_id


# Database models
class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    system_id: Mapped[int] = mapped_column(Integer, ForeignKey("systems.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(String(5000), nullable=False)

    # Relationships
    team = relationship("Team", back_populates="policies")
    system = relationship("System", back_populates="policies")

    def to_prompt(self) -> List[str]:
        return [json.dumps(model_to_dict(self), indent=4, default=str)]

    def update(self):
        db = next(get_db())
        db.merge(self)
        db.commit()


def get_system_policy_prompts(agent_id_str: str) -> List[str]:
    """Get all policies where the system_id matches the system_id"""
    db = next(get_db())
    try:
        system = get_system_from_agent_id(agent_id_str)
        if system is None:
            return ["No system policies found - system not registered in database."]
        team_id = system.team_id
        prompts = []
        prompts.extend(
            policy.to_prompt()
            for policy in db.query(Policy)
            .filter(
                or_(
                    Policy.system_id == system.id,
                    and_(Policy.team_id == team_id, Policy.system_id.is_(None)),
                )
            )
            .all()
        )
        return prompts
    finally:
        db.close()


def get_team_policy_prompts(agent_id_str: str) -> List[str]:
    """Get all policies where the team_id matches and system_id is None"""
    db = next(get_db())
    try:
        system = get_system_from_agent_id(agent_id_str)
        if system is None:
            return ["No team policies found - system not registered in database."]
        team_id = system.team_id
        prompts = []
        prompts.extend(
            policy.to_prompt()
            for policy in db.query(Policy)
            .filter(
                and_(Policy.team_id == team_id, Policy.system_id.is_(None)),
            )
            .all()
        )
        return prompts
    finally:
        db.close()


def get_policy(policy_id: int) -> Policy:
    """Get policy by ID from database"""
    db = next(get_db())
    try:
        return db.query(Policy).filter(Policy.id == policy_id).first()
    finally:
        db.close()
