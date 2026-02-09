from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.cli.env_loader import load_op_service_account_token


def test_has_onepassword_auth_prefers_repo_env_service_token_over_existing_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "stale-global-token")
    monkeypatch.delenv("OP_SESSION_CYBERAGENT", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "OP_SERVICE_ACCOUNT_TOKEN=repo-service-token\n", encoding="utf-8"
    )

    assert onboarding_cli._has_onepassword_auth() is True
    assert os.environ.get("OP_SERVICE_ACCOUNT_TOKEN") == "repo-service-token"


def test_load_op_service_account_token_prefers_repo_env_over_existing_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "stale-global-token")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "OP_SERVICE_ACCOUNT_TOKEN=repo-service-token\n", encoding="utf-8"
    )

    load_op_service_account_token()

    assert os.environ.get("OP_SERVICE_ACCOUNT_TOKEN") == "repo-service-token"
