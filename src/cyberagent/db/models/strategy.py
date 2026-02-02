"""
Strategy model and database operations
"""

import json
from typing import List

from sqlalchemy import Enum, ForeignKey, Integer, String, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.cyberagent.db.db_utils import get_db
from src.enums import Status
from src.cyberagent.db.init_db import Base
from src.cyberagent.db.models.initiative import Initiative
from src.cyberagent.domain.serialize import model_to_dict


# Database models
class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    purpose_id: Mapped[int] = mapped_column(Integer, ForeignKey("purposes.id"))
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.PENDING)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(5000), nullable=False)
    result: Mapped[str | None] = mapped_column(String(5000))

    # Relationships
    team = relationship("Team", back_populates="strategies")
    purpose = relationship("Purpose", back_populates="strategies")
    initiatives = relationship("Initiative", back_populates="strategy")

    def get_initiatives(self) -> List[Initiative]:
        db = next(get_db())
        try:
            return db.query(Initiative).filter(Initiative.strategy_id == self.id).all()
        finally:
            db.close()

    def set_status(self, status: Status | str):
        self.status = Status(status)

    def to_prompt(self) -> List[str]:
        return [json.dumps(model_to_dict(self), indent=4, default=str)]

    def update(self):
        db = next(get_db())
        db.merge(self)
        db.commit()

    def add(self) -> int:
        db = next(get_db())
        db.add(self)
        db.flush()
        db.commit()
        db.refresh(self)
        db.expunge(self)
        return self.id


def get_strategy(strategy_id: int) -> Strategy:
    db = next(get_db())
    try:
        return db.query(Strategy).filter(Strategy.id == strategy_id).first()
    finally:
        db.close()


def get_teams_active_strategy(team_id: int) -> Strategy:
    db = next(get_db())
    try:
        return (
            db.query(Strategy)
            .filter(
                and_(
                    Strategy.status == Status.IN_PROGRESS,
                    Strategy.team_id == team_id,
                )
            )
            .first()
        )
    finally:
        db.close()
