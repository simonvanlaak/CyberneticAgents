"""Procedure (Standard Operating Procedure) model."""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import Base
from src.cyberagent.domain.serialize import model_to_dict
from src.enums import ProcedureStatus


class Procedure(Base):
    __tablename__ = "procedures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(5000), nullable=False)
    status: Mapped[ProcedureStatus] = mapped_column(
        Enum(ProcedureStatus), default=ProcedureStatus.DRAFT
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    series_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    risk_level: Mapped[str] = mapped_column(String(100), nullable=False)
    impact: Mapped[str] = mapped_column(String(1000), nullable=False)
    rollback_plan: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_system_id: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_by_system_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow
    )

    team = relationship("Team", back_populates="procedures")
    tasks = relationship("ProcedureTask", back_populates="procedure")
    runs = relationship("ProcedureRun", back_populates="procedure")

    def to_prompt(self) -> List[str]:
        return [json.dumps(model_to_dict(self), indent=4, default=str)]

    def update(self) -> None:
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


def get_procedure(procedure_id: int) -> Procedure:
    db = next(get_db())
    try:
        return db.query(Procedure).filter(Procedure.id == procedure_id).first()
    finally:
        db.close()
