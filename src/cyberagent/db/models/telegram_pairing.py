from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.cyberagent.db.init_db import Base


class TelegramPairing(Base):
    __tablename__ = "telegram_pairings"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_telegram_pairing_user"),
        UniqueConstraint("pairing_code", name="uq_telegram_pairing_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chat_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    pairing_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, nullable=False
    )
    approved_by_chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    denied_by_chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    denied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
