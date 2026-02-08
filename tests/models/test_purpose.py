import uuid

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import init_db
from src.cyberagent.db.models.purpose import Purpose, get_or_create_default_purpose
from src.cyberagent.db.models.team import Team


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


def test_get_or_create_default_purpose_reuses_existing_non_default_name():
    init_db()
    team_id = _create_team_id()
    purpose = Purpose(
        team_id=team_id,
        name="Onboarding SOP",
        content="Custom purpose content.",
    )
    purpose_id = purpose.add()

    reused = get_or_create_default_purpose(team_id)

    db = next(get_db())
    try:
        purpose_count = db.query(Purpose).filter(Purpose.team_id == team_id).count()
    finally:
        db.close()

    assert reused.id == purpose_id
    assert purpose_count == 1


def test_get_or_create_default_purpose_deduplicates_team_purposes():
    init_db()
    team_id = _create_team_id()
    primary = Purpose(
        team_id=team_id,
        name="Onboarding SOP",
        content="Primary purpose.",
    )
    primary_id = primary.add()
    secondary = Purpose(
        team_id=team_id,
        name="Default Purpose",
        content="Secondary purpose.",
    )
    secondary_id = secondary.add()

    db = next(get_db())
    try:
        from src.cyberagent.db.models.strategy import Strategy

        strategy = Strategy(
            team_id=team_id,
            purpose_id=secondary_id,
            name="Strategy on secondary purpose",
            description="desc",
        )
        db.add(strategy)
        db.commit()
        strategy_id = strategy.id
    finally:
        db.close()

    reused = get_or_create_default_purpose(team_id)

    db = next(get_db())
    try:
        from src.cyberagent.db.models.strategy import Strategy

        purpose_count = db.query(Purpose).filter(Purpose.team_id == team_id).count()
        migrated_strategy = (
            db.query(Strategy).filter(Strategy.id == strategy_id).first()
        )
    finally:
        db.close()

    assert reused.id == primary_id
    assert purpose_count == 1
    assert migrated_strategy is not None
    assert migrated_strategy.purpose_id == primary_id
