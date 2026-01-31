import uuid

from src.db_utils import get_db
from src.init_db import init_db
from src.models.purpose import Purpose, get_or_create_default_purpose
from src.models.team import Team


def _create_team_id() -> int:
    team = Team(name=f"purpose_team_{uuid.uuid4().hex}")
    db = next(get_db())
    db.add(team)
    db.commit()
    return team.id


def test_purpose_add_persists_and_returns_id():
    init_db()
    team_id = _create_team_id()
    purpose = Purpose(
        team_id=team_id,
        name="Purpose",
        content="Purpose content.",
    )

    result = purpose.add()

    assert result is not None


def test_get_or_create_default_purpose_returns_existing():
    init_db()
    team_id = _create_team_id()
    purpose = Purpose(
        team_id=team_id,
        name="Default Purpose",
        content="Default purpose content.",
    )
    purpose_id = purpose.add()

    existing = get_or_create_default_purpose(team_id)

    assert existing.id == purpose_id
