import re

from src.agents.message_builders import build_initiative_assign_message


def test_build_initiative_assign_message_uses_safe_source_identifier() -> None:
    message = build_initiative_assign_message(12)

    assert message.initiative_id == 12
    assert message.source
    assert re.fullmatch(r"[A-Za-z0-9_-]+", message.source) is not None
