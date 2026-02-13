"""
Strategy model and database operations
"""

import json
from typing import List

from sqlalchemy import Enum, ForeignKey, Integer, String, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship

import warnings

from src.enums import Status
from src.cyberagent.db.init_db import Base
from src.cyberagent.db.session_context import managed_session
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
        with managed_session() as db:
            return db.query(Initiative).filter(Initiative.strategy_id == self.id).all()

    def set_status(self, status: Status | str):
        self.status = Status(status)

    def to_prompt(self) -> List[str]:
        return [json.dumps(model_to_dict(self), indent=4, default=str)]

    def update(self):
        warnings.warn(
            "Strategy.update() is deprecated; persist via service-layer helpers.",
            DeprecationWarning,
            stacklevel=2,
        )
        with managed_session(commit=True) as db:
            db.merge(self)

    def add(self) -> int:
        warnings.warn(
            "Strategy.add() is deprecated; persist via service-layer helpers.",
            DeprecationWarning,
            stacklevel=2,
        )
        with managed_session() as db:
            db.add(self)
            db.flush()
            db.commit()
            db.refresh(self)
            db.expunge(self)
            return self.id


def get_strategy(strategy_id: int) -> Strategy:
    with managed_session() as db:
        return db.query(Strategy).filter(Strategy.id == strategy_id).first()


def get_teams_active_strategy(team_id: int) -> Strategy:
    with managed_session() as db:
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
