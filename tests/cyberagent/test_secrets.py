import os

import pytest

from src.cyberagent import secrets


def test_has_onepassword_auth_accepts_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.setenv("OP_SESSION_CYBERAGENT", "session-token")

    assert secrets.has_onepassword_auth() is True


def test_get_secret_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMPLE_SECRET", "env-value")

    def _fail_load(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Vault lookup should not be called when env is set.")

    monkeypatch.setattr(secrets, "load_secret_from_1password", _fail_load)

    assert secrets.get_secret("EXAMPLE_SECRET") == "env-value"


def test_get_secret_reads_onepassword(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXAMPLE_SECRET", raising=False)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "token")
    monkeypatch.setattr(
        secrets, "load_secret_from_1password", lambda *_args, **_kwargs: "vault-value"
    )

    assert secrets.get_secret("EXAMPLE_SECRET") == "vault-value"
    assert os.environ.get("EXAMPLE_SECRET") == "vault-value"
