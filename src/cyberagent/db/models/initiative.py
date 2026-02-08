"""
Initiative model and database operations
"""

import json
from typing import List, Optional

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy.orm.base import Mapped

from src.agents.messages import InitiativeAssignMessage
from src.cyberagent.db.db_utils import get_db
from src.enums import Status
from src.cyberagent.db.init_db import Base
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

    def get_assign_message(self) -> InitiativeAssignMessage:
        self.status = Status(Status.PENDING)
        source = f"initiative_{self.id}" if self.id is not None else "initiative"

        return InitiativeAssignMessage(
            initiative_id=self.id,
            source=source,
            content=f"Start initiative {self.id}.",
        )

    def to_prompt(self) -> List[str]:
        return [json.dumps(model_to_dict(self), indent=4, default=str)]

    def get_tasks(self) -> List[Task]:
        db = next(get_db())
        try:
            return db.query(Task).filter(Task.initiative_id == self.id).all()
        finally:
            db.close()

    def add(self) -> int:
        db = next(get_db())
        db.add(self)
        db.flush()
        db.commit()
        db.refresh(self)
        db.expunge(self)
        return self.id

    def set_status(self, status: Status | str) -> None:
        self.status = Status(status)

    def update(self):
        db = next(get_db())
        db.merge(self)
        db.commit()


def get_initiative(initiative_id: int) -> Initiative:
    """Get initiative by ID from database"""
    db = next(get_db())
    try:
        return db.query(Initiative).filter(Initiative.id == initiative_id).first()
    finally:
        db.close()
