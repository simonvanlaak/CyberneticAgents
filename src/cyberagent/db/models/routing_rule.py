from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.cyberagent.db.init_db import Base


class RoutingRule(Base):
    __tablename__ = "routing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    targets_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_system_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by_system_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))

    def filters(self) -> dict[str, str]:
        try:
            value = json.loads(self.filters_json)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def targets(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.targets_json)
        except json.JSONDecodeError:
            return []
        return value if isinstance(value, list) else []
