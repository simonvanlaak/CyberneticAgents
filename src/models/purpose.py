"""
Purpose model and database operations
"""

import json
from typing import List

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db_utils import get_db
from src.init_db import Base
from src.models.strategy import Strategy


class Purpose(Base):
    __tablename__ = "purposes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(String(5000), nullable=False)

    # Relationships
    team = relationship("Team", back_populates="purposes")
    strategies = relationship("Strategy", back_populates="purpose")

    def to_prompt(self) -> List[str]:
        return [json.dumps(self.__dict__, indent=4)]

    def get_strategies(self) -> List[Strategy]:
        db = next(get_db())
        try:
            return db.query(Strategy).filter(Strategy.purpose_id == self.id).first()
        finally:
            db.close()

    def update(self):
        db = next(get_db())
        db.commit()

    def add(self) -> int:
        db = next(get_db())
        db.add(self)
        db.flush()
        new_id = self.id
        db.commit()
        return new_id


def get_purpose(purpose_id: int) -> Purpose:
    db = next(get_db())
    try:
        return db.query(Purpose).filter(Purpose.id == purpose_id).first()
    finally:
        db.close()


def get_or_create_default_purpose(team_id: int) -> Purpose:
    db = next(get_db())
    try:
        purpose = (
            db.query(Purpose)
            .filter(
                Purpose.team_id == team_id,
                Purpose.name == "Default Purpose",
            )
            .first()
        )
        if purpose:
            return purpose
        purpose = Purpose(
            team_id=team_id,
            name="Default Purpose",
            content="Default purpose content.",
        )
        db.add(purpose)
        db.commit()
        return purpose
    finally:
        db.close()
