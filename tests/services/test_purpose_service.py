import pytest


def test_get_or_create_default_purpose_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.cyberagent.services import purposes as purpose_service

    monkeypatch.setattr(
        purpose_service, "_get_or_create_default_purpose", lambda team_id: "purpose"
    )

    assert purpose_service.get_or_create_default_purpose(1) == "purpose"
