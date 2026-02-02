"""Procedure task template model."""

from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import Base
from src.cyberagent.domain.serialize import model_to_dict


class ProcedureTask(Base):
    __tablename__ = "procedure_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    procedure_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("procedures.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    depends_on_task_id: Mapped[Optional[int]] = mapped_column(Integer)
    default_assignee_system_type: Mapped[Optional[str]] = mapped_column(String(100))
    required_skills: Mapped[Optional[str]] = mapped_column(Text)

    procedure = relationship("Procedure", back_populates="tasks")

    def to_prompt(self) -> List[str]:
        return [json.dumps(model_to_dict(self), indent=4, default=str)]

    def add(self) -> int:
        db = next(get_db())
        db.add(self)
        db.flush()
        db.commit()
        db.refresh(self)
        db.expunge(self)
        return self.id


def get_procedure_task(task_id: int) -> ProcedureTask:
    db = next(get_db())
    try:
        return db.query(ProcedureTask).filter(ProcedureTask.id == task_id).first()
    finally:
        db.close()
