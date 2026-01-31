"""
Initiative model and database operations
"""

import json
from typing import List, Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy.orm.base import Mapped

from src.agents.messages import InitiativeAssignMessage
from src.db_utils import get_db
from src.enums import Status
from src.init_db import Base
from src.models.task import Task


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
    status: Mapped[Status] = mapped_column(Status, default=Status.PENDING)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(5000), nullable=False)
    result: Mapped[Optional[str]] = mapped_column(String(5000))

    # Relationships
    team = relationship("Team", back_populates="initiatives")
    strategy = relationship("Strategy", back_populates="initiatives")
    tasks = relationship("Task", back_populates="initiative")

    def get_assign_message(self):
        self.status = Status(Status.PENDING)

        return InitiativeAssignMessage(
            initiative_id=self.id,
            source=self.name,
            content=f"Start initiative {self.id}.",
        )

    def to_prompt(self) -> List[str]:
        return [json.dumps(self.__dict__, indent=4)]

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
        new_id = self.id
        db.commit()
        return new_id

    def set_status(self, status: str) -> None:
        self.status = Status(status)

    def update(self):
        db = next(get_db())
        db.commit()


def get_initiative(initiative_id: int) -> Initiative:
    """Get initiative by ID from database"""
    db = next(get_db())
    try:
        return db.query(Initiative).filter(Initiative.id == initiative_id).first()
    finally:
        db.close()
