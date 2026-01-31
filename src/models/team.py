import json
from typing import List

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db_utils import get_db
from src.init_db import Base


# Database models
class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Relationships - using string references to avoid circular imports
    systems = relationship("System", back_populates="team")
    tasks = relationship("Task", back_populates="team")
    initiatives = relationship("Initiative", back_populates="team")
    strategies = relationship("Strategy", back_populates="team")
    purposes = relationship("Purpose", back_populates="team")
    policies = relationship("Policy", back_populates="team")

    def to_prompt(self) -> List[str]:
        return [json.dumps(self.dict(), indent=4)]

    def update(self):
        db = next(get_db())
        db.commit()


def get_team(team_id: int) -> Team:
    """Get team by ID from database"""
    db = next(get_db())
    try:
        return db.query(Team).filter(Team.id == team_id).first()
    finally:
        db.close()
