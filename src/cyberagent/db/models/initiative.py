"""
Initiative model and database operations
"""

import json
from typing import List, Optional

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy.orm.base import Mapped

import warnings

from src.enums import Status
from src.cyberagent.db.init_db import Base
from src.cyberagent.db.session_context import managed_session
from src.cyberagent.db.models.task import Task
from src.cyberagent.domain.serialize import model_to_dict


# Database models
class Initiative(Base):
    __tablename__ = "initiatives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    strategy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strategies.id"), nullable=False
    )
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.PENDING)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(5000), nullable=False)
    result: Mapped[Optional[str]] = mapped_column(String(5000))
    procedure_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("procedures.id")
    )
    procedure_version: Mapped[Optional[int]] = mapped_column(Integer)

    # Relationships
    team = relationship("Team", back_populates="initiatives")
    strategy = relationship("Strategy", back_populates="initiatives")
    tasks = relationship("Task", back_populates="initiative")
    procedure = relationship("Procedure")

    def to_prompt(self) -> List[str]:
        return [json.dumps(model_to_dict(self), indent=4, default=str)]

    def get_tasks(self) -> List[Task]:
        with managed_session() as db:
            return db.query(Task).filter(Task.initiative_id == self.id).all()

    def add(self) -> int:
        warnings.warn(
            "Initiative.add() is deprecated; persist via service-layer helpers.",
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

    def set_status(self, status: Status | str) -> None:
        self.status = Status(status)

    def update(self):
        warnings.warn(
            "Initiative.update() is deprecated; persist via service-layer helpers.",
            DeprecationWarning,
            stacklevel=2,
        )
        with managed_session(commit=True) as db:
            db.merge(self)


def get_initiative(initiative_id: int) -> Initiative:
    """Get initiative by ID from database"""
    with managed_session() as db:
        return db.query(Initiative).filter(Initiative.id == initiative_id).first()
