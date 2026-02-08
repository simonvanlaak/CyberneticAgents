import re

from src.cyberagent.db.models.initiative import Initiative


def test_get_assign_message_uses_safe_source_identifier() -> None:
    initiative = Initiative(
        team_id=1,
        strategy_id=1,
        name="Thesis Scope & Requirements Assessment",
        description="Collect requirements",
    )
    initiative.id = 12

    message = initiative.get_assign_message()

    assert message.initiative_id == 12
    assert message.source
    assert re.fullmatch(r"[A-Za-z0-9_-]+", message.source) is not None
