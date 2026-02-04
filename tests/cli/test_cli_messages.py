from __future__ import annotations

import pytest

from src.cyberagent.cli.message_catalog import get_message


def test_get_message_formats_placeholders() -> None:
    message = get_message(
        "onboarding",
        "team_created",
        team_name="Alpha",
        team_id=7,
    )

    assert message == "Created default team: Alpha (id=7)."


def test_get_message_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        get_message("onboarding", "unknown_key")
