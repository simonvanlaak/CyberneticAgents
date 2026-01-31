import time

from src.db_utils import get_db
from src.init_db import init_db
from src.models.initiative import Initiative
from src.models.purpose import Purpose
from src.models.strategy import Strategy
from src.models.team import Team


def _create_team_id() -> int:
    team = Team(name=f"test_team_{time.time_ns()}")
    db = next(get_db())
    db.add(team)
    db.commit()
    team_id = team.id
    return team_id


def _create_purpose_id(team_id: int) -> int:
    purpose = Purpose(
        team_id=team_id,
        name="Default Purpose",
        content="Default purpose content.",
    )
    db = next(get_db())
    db.add(purpose)
    db.commit()
    return purpose.id


def test_strategy_add_persists_and_returns_id():
    init_db()
    team_id = _create_team_id()
    purpose_id = _create_purpose_id(team_id)
    strategy = Strategy(
        team_id=team_id,
        purpose_id=purpose_id,
        name="Name",
        description="Desc",
        result="",
    )

    result = strategy.add()

    assert result is not None


def test_initiative_add_persists_and_returns_id():
    init_db()
    team_id = _create_team_id()
    purpose_id = _create_purpose_id(team_id)
    strategy = Strategy(
        team_id=team_id,
        purpose_id=purpose_id,
        name="Name",
        description="Desc",
        result="",
    )
    strategy_id = strategy.add()
    initiative = Initiative(
        team_id=team_id,
        strategy_id=strategy_id,
        name="Init",
        description="Desc",
    )

    result = initiative.add()

    assert result is not None
