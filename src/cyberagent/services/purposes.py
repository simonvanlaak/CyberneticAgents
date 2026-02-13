"""Purpose helpers."""

from __future__ import annotations

from src.cyberagent.db.models.purpose import (
    Purpose,
    get_or_create_default_purpose as _get_or_create_default_purpose,
)
from src.cyberagent.db.session_context import managed_session


def get_or_create_default_purpose(team_id: int):
    """Return the default purpose for a team, creating it if needed."""
    return _get_or_create_default_purpose(team_id)


def update_purpose_fields(
    purpose: Purpose,
    *,
    name: str | None = None,
    content: str | None = None,
) -> None:
    """Persist purpose field updates through the service layer."""

    if name is not None:
        purpose.name = name
    if content is not None:
        purpose.content = content

    if isinstance(purpose, Purpose):
        with managed_session(commit=True) as session:
            session.merge(purpose)
        return

    update_callable = getattr(purpose, "update", None)
    if callable(update_callable):
        update_callable()
