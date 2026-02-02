import os

import pytest

from src.cyberagent.tools.cli_executor import secrets


def test_get_tool_secrets_uses_hardcoded_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "brave")
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")

    result = secrets.get_tool_secrets("web_search")

    assert result == {"BRAVE_API_KEY": "brave"}


def test_get_tool_secrets_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")
    monkeypatch.setattr(secrets, "_load_secret_from_1password", lambda **_: None)

    with pytest.raises(ValueError, match="Missing required secrets for tool"):
        secrets.get_tool_secrets("web_search")


def test_get_tool_secrets_returns_empty_for_unknown_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = secrets.get_tool_secrets("unknown")

    assert result == {}


def test_get_tool_secrets_requires_onepassword(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "brave")
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)

    with pytest.raises(ValueError, match="1Password authentication"):
        secrets.get_tool_secrets("web_search")


def test_tool_secret_env_vars_contains_web_search() -> None:
    assert secrets.TOOL_SECRET_ENV_VARS["web_search"] == ["BRAVE_API_KEY"]


def test_get_tool_secrets_loads_from_onepassword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")
    monkeypatch.setattr(secrets, "_load_secret_from_1password", lambda **_: "brave")

    result = secrets.get_tool_secrets("web_search")

    assert result == {"BRAVE_API_KEY": "brave"}
