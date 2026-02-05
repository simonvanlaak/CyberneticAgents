from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.cyberagent.db.init_db import Base


class DeadLetterMessage(Base):
    __tablename__ = "dead_letter_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    handled_by_system_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def payload(self) -> dict[str, Any]:
        try:
            value = json.loads(self.payload_json)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}
