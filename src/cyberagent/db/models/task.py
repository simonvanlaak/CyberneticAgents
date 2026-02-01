"""
Task model and database operations
"""

import json
from typing import List, Optional

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy.orm.base import Mapped

from src.cyberagent.db.db_utils import get_db
from src.enums import Status
from src.cyberagent.db.init_db import Base
from src.cyberagent.domain.serialize import model_to_dict


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    initiative_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("initiatives.id")
    )
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.PENDING)
    assignee: Mapped[Optional[str]] = mapped_column(String(100))  # AgentId as string
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    team = relationship("Team", back_populates="tasks")
    initiative = relationship("Initiative", back_populates="tasks")

    def set_status(self, status: str):
        self.status = Status(status)

    def to_prompt(self) -> List[str]:
        return [json.dumps(model_to_dict(self), indent=4, default=str)]

    def update(self):
        db = next(get_db())
        db.merge(self)
        db.commit()

    def add(self):
        db = next(get_db())
        db.add(self)
        db.commit()
        db.refresh(self)
        db.expunge(self)
        return self.id


def get_task(task_id: int) -> Task:
    """Get task by ID from database"""
    db = next(get_db())
    try:
        return db.query(Task).filter(Task.id == task_id).first()
    finally:
        db.close()
