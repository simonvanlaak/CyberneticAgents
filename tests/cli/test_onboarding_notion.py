from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.cli import onboarding_optional
from src.cyberagent.cli import onboarding_pkm


def _base_args() -> argparse.Namespace:
    return argparse.Namespace(
        user_name="Test User",
        pkm_source="notion",
        repo_url="",
        profile_links=["https://example.com/profile"],
        token_env="GITHUB_READONLY_TOKEN",
        token_username="x-access-token",
    )


def test_validate_onboarding_inputs_notion_ready_from_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = _base_args()
    monkeypatch.setenv("NOTION_API_KEY", "token")
    monkeypatch.setattr(
        onboarding_pkm,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("Should not load")),
    )

    assert onboarding_cli._validate_onboarding_inputs(args) is True
    captured = capsys.readouterr().out
    assert "Notion is ready." in captured


def test_validate_onboarding_inputs_notion_ready_from_1password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = _base_args()
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.setattr(
        onboarding_pkm,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: ("token", None),
    )
    monkeypatch.setattr(
        onboarding_pkm,
        "prompt_store_secret_in_1password",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("Should not prompt")),
    )

    assert onboarding_cli._validate_onboarding_inputs(args) is True
    captured = capsys.readouterr().out
    assert "Notion is ready." in captured
    assert os.environ.get("NOTION_API_KEY") == "token"


def test_validate_onboarding_inputs_notion_prompt_declined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = _base_args()
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.setattr(
        onboarding_pkm,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: (None, None),
    )
    monkeypatch.setattr(
        onboarding_pkm,
        "prompt_store_secret_in_1password",
        lambda **_kwargs: False,
    )

    assert onboarding_cli._validate_onboarding_inputs(args) is False


def test_validate_onboarding_inputs_notion_prompt_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = _base_args()
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    results = iter([(None, None), ("token", None)])

    def _load_secret(**_kwargs: object) -> tuple[str | None, str | None]:
        return next(results)

    prompt_calls: list[bool] = []

    def _prompt_store(**_kwargs: object) -> bool:
        prompt_calls.append(True)
        return True

    monkeypatch.setattr(
        onboarding_pkm, "load_secret_from_1password_with_error", _load_secret
    )
    monkeypatch.setattr(
        onboarding_pkm, "prompt_store_secret_in_1password", _prompt_store
    )

    assert onboarding_cli._validate_onboarding_inputs(args) is True
    assert prompt_calls == [True]
    captured = capsys.readouterr().out
    assert "Notion is ready." in captured
    assert os.environ.get("NOTION_API_KEY") == "token"


def test_check_onboarding_repo_token_reports_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITHUB_READONLY_TOKEN", raising=False)
    monkeypatch.setattr(
        onboarding_cli,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: (None, "missing"),
    )

    assert onboarding_cli._check_onboarding_repo_token() is True
    captured = capsys.readouterr().out
    assert "GITHUB_READONLY_TOKEN" in captured


def test_warn_optional_api_keys_reports_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for key in ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGSMITH_API_KEY"]:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setattr(
        onboarding_optional,
        "load_secret_from_1password",
        lambda **_kwargs: None,
    )

    onboarding_optional._warn_optional_api_keys()
    captured = capsys.readouterr().out
    assert "LANGFUSE_PUBLIC_KEY" in captured
    assert "LANGFUSE_SECRET_KEY" in captured
    assert "LANGSMITH_API_KEY" in captured


def test_offer_optional_telegram_setup_uses_existing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(
        onboarding_optional.onboarding_telegram.sys.stdin, "isatty", lambda: True
    )

    username_called: list[bool] = []
    webhook_called: list[bool] = []

    monkeypatch.setattr(
        onboarding_optional.onboarding_telegram,
        "_offer_optional_telegram_username_setup",
        lambda: username_called.append(True),
    )
    monkeypatch.setattr(
        onboarding_optional,
        "_offer_optional_telegram_webhook_setup",
        lambda: webhook_called.append(True),
    )

    onboarding_optional._offer_optional_telegram_setup()
    assert username_called == [True]
    assert webhook_called == [True]


def test_ensure_repo_root_env_var_writes_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("FOO=bar\n", encoding="utf-8")
    monkeypatch.setattr(onboarding_cli, "_repo_root", lambda: tmp_path)
    monkeypatch.delenv("CYBERAGENT_ROOT", raising=False)

    onboarding_cli._ensure_repo_root_env_var()

    assert "CYBERAGENT_ROOT" in env_path.read_text(encoding="utf-8")
    assert os.environ.get("CYBERAGENT_ROOT") == str(tmp_path.resolve())


def test_check_required_tool_secrets_no_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(onboarding_cli, "load_skill_definitions", lambda *_: [])

    assert onboarding_cli._check_required_tool_secrets() is True


def test_check_network_access_allowed_when_probe_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Skill:
        name = "web-search"

    monkeypatch.setattr(onboarding_cli, "load_skill_definitions", lambda *_: [_Skill()])
    monkeypatch.setattr(onboarding_cli, "_probe_network_access", lambda: True)

    assert onboarding_cli._check_network_access() is True
