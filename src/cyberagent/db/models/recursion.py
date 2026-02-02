from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.cyberagent.db.init_db import Base


class Recursion(Base):
    __tablename__ = "recursions"

    sub_team_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origin_system_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    parent_team_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
