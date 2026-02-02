"""Procedure run model."""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import Base
from src.cyberagent.domain.serialize import model_to_dict


class ProcedureRun(Base):
    __tablename__ = "procedure_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    procedure_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("procedures.id"), nullable=False
    )
    procedure_version: Mapped[int] = mapped_column(Integer, nullable=False)
    initiative_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("initiatives.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="started")
    executed_by_system_id: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False))

    procedure = relationship("Procedure", back_populates="runs")
    initiative = relationship("Initiative")

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


def get_procedure_run(run_id: int) -> ProcedureRun:
    db = next(get_db())
    try:
        return db.query(ProcedureRun).filter(ProcedureRun.id == run_id).first()
    finally:
        db.close()
