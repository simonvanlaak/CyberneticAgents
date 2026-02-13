"""
Purpose model and database operations
"""

import json
from typing import List

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

import warnings

from src.cyberagent.db.init_db import Base
from src.cyberagent.db.session_context import managed_session
from src.cyberagent.domain.serialize import model_to_dict
from src.cyberagent.db.models.strategy import Strategy

DEFAULT_PURPOSE_NAME = "Default Purpose"
DEFAULT_PURPOSE_CONTENT = (
    "Stay viable by creating more value for the user than the cost incurred."
)
LEGACY_DEFAULT_PURPOSE_CONTENT = "Default purpose content."


class Purpose(Base):
    __tablename__ = "purposes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(String(5000), nullable=False)

    # Relationships
    team = relationship("Team", back_populates="purposes")
    strategies = relationship("Strategy", back_populates="purpose")

    def to_prompt(self) -> List[str]:
        return [json.dumps(model_to_dict(self), indent=4, default=str)]

    def get_strategies(self) -> List[Strategy]:
        with managed_session() as db:
            return db.query(Strategy).filter(Strategy.purpose_id == self.id).first()

    def update(self):
        warnings.warn(
            "Purpose.update() is deprecated; persist via service-layer helpers.",
            DeprecationWarning,
            stacklevel=2,
        )
        with managed_session(commit=True) as db:
            db.merge(self)

    def add(self) -> int:
        warnings.warn(
            "Purpose.add() is deprecated; persist via service-layer helpers.",
            DeprecationWarning,
            stacklevel=2,
        )
        with managed_session() as db:
            db.add(self)
            db.flush()
            db.commit()
            db.refresh(self)
            db.expunge(self)
            return self.id


def get_purpose(purpose_id: int) -> Purpose:
    with managed_session() as db:
        return db.query(Purpose).filter(Purpose.id == purpose_id).first()


def get_or_create_default_purpose(team_id: int) -> Purpose:
    with managed_session() as db:
        purposes = (
            db.query(Purpose)
            .filter(Purpose.team_id == team_id)
            .order_by(Purpose.id.asc())
            .all()
        )
        if purposes:
            primary = purposes[0]
            duplicates = purposes[1:]
            for duplicate in duplicates:
                db.query(Strategy).filter(Strategy.purpose_id == duplicate.id).update(
                    {"purpose_id": primary.id}
                )
                db.delete(duplicate)
            should_update_default = (
                primary.name == DEFAULT_PURPOSE_NAME
                and primary.content == LEGACY_DEFAULT_PURPOSE_CONTENT
            )
            if should_update_default:
                primary.content = DEFAULT_PURPOSE_CONTENT
            if duplicates or should_update_default:
                db.commit()
                db.refresh(primary)
            db.expunge(primary)
            return primary
        purpose = Purpose(
            team_id=team_id,
            name=DEFAULT_PURPOSE_NAME,
            content=DEFAULT_PURPOSE_CONTENT,
        )
        db.add(purpose)
        db.commit()
        db.refresh(purpose)
        db.expunge(purpose)
        return purpose
