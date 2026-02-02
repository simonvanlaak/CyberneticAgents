from __future__ import annotations

import argparse
import pytest

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.team import Team


def _clear_teams() -> None:
    session = next(get_db())
    try:
        session.query(Team).delete()
        session.commit()
    finally:
        session.close()


def test_handle_onboarding_creates_default_team(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_teams()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)

    exit_code = onboarding_cli.handle_onboarding(
        argparse.Namespace(), 'cyberagent suggest "Describe the task"'
    )
    captured = capsys.readouterr().out
    monkeypatch.undo()

    assert exit_code == 0
    assert "Created default team" in captured
    assert "cyberagent suggest" in captured

    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == "root").first()
        assert team is not None
    finally:
        session.close()


def test_handle_onboarding_skips_when_team_exists(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_teams()
    session = next(get_db())
    try:
        session.add(Team(name="existing_team"))
        session.commit()
    finally:
        session.close()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    exit_code = onboarding_cli.handle_onboarding(
        argparse.Namespace(), 'cyberagent suggest "Describe the task"'
    )
    captured = capsys.readouterr().out
    monkeypatch.undo()

    assert exit_code == 0
    assert "Team already exists" in captured
    assert "cyberagent suggest" in captured

    session = next(get_db())
    try:
        assert session.query(Team).count() == 1
    finally:
        session.close()


def test_handle_onboarding_requires_technical_checks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()

    monkeypatch.setattr(
        onboarding_cli, "run_technical_onboarding_checks", lambda: False
    )

    exit_code = onboarding_cli.handle_onboarding(
        argparse.Namespace(), 'cyberagent suggest "Describe the task"'
    )
    captured = capsys.readouterr().out

    assert exit_code == 1
    assert "technical onboarding" in captured.lower()


def test_technical_onboarding_requires_groq_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setattr(onboarding_cli, "_is_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "_check_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "_check_docker_available", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_skill_root_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_required_tool_secrets", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)
    monkeypatch.setattr(
        onboarding_cli, "_load_technical_onboarding_state", lambda: None
    )
    monkeypatch.setattr(
        onboarding_cli, "_save_technical_onboarding_state", lambda *_: None
    )
    monkeypatch.setattr(onboarding_cli, "_prompt_yes_no", lambda *_: False)

    assert onboarding_cli.run_technical_onboarding_checks() is False
    captured = capsys.readouterr().out
    assert "GROQ_API_KEY" in captured


def test_technical_onboarding_requires_onepassword_auth(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setattr(onboarding_cli, "_is_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "_check_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "_check_docker_available", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_skill_root_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_required_tool_secrets", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: False)
    monkeypatch.setattr(
        onboarding_cli, "_load_technical_onboarding_state", lambda: None
    )
    monkeypatch.setattr(
        onboarding_cli, "_save_technical_onboarding_state", lambda *_: None
    )

    assert onboarding_cli.run_technical_onboarding_checks() is False
    captured = capsys.readouterr().out
    assert "1Password service account token" in captured


def test_onepassword_hint_when_op_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: False)
    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: None)

    assert onboarding_cli._check_onepassword_auth() is False
    captured = capsys.readouterr().out
    assert "OP_SERVICE_ACCOUNT_TOKEN" in captured


def test_missing_brave_key_explains_vault_and_item(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)
    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/op")

    def _load_secret(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(onboarding_cli, "_load_secret_from_1password", _load_secret)
    monkeypatch.setattr(onboarding_cli, "_prompt_yes_no", lambda *_: False)

    assert onboarding_cli._check_required_tool_secrets() is False
    captured = capsys.readouterr().out
    assert "CyberneticAgents" in captured
    assert "BRAVE_API_KEY" in captured


def test_prompt_store_secret_creates_vault_and_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    class DummyResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd: list[str], **kwargs) -> DummyResult:  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["op", "item", "create"] and "--format" in cmd:
            return DummyResult(returncode=0, stdout='{"id":"check"}')
        if cmd[:3] == ["op", "item", "delete"]:
            return DummyResult(returncode=0)
        if cmd[:3] == ["op", "vault", "get"]:
            return DummyResult(returncode=1)
        if cmd[:3] == ["op", "vault", "create"]:
            return DummyResult(returncode=0)
        if cmd[:3] == ["op", "item", "create"]:
            return DummyResult(returncode=0)
        return DummyResult(returncode=0)

    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/op")
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_prompt_yes_no", lambda *_: True)
    monkeypatch.setattr(onboarding_cli.getpass, "getpass", lambda *_: "secret")
    monkeypatch.setattr(onboarding_cli.subprocess, "run", fake_run)

    assert (
        onboarding_cli._prompt_store_secret_in_1password(
            env_name="BRAVE_API_KEY",
            description="Brave Search API key",
            doc_hint=None,
        )
        is True
    )
    assert ["op", "vault", "get", "CyberneticAgents"] in calls
    assert ["op", "vault", "create", "CyberneticAgents"] in calls
    assert any(cmd[:3] == ["op", "item", "create"] for cmd in calls)
    assert any("--title" in cmd and "BRAVE_API_KEY" in cmd for cmd in calls)


def test_prompt_store_secret_requires_write_access(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class DummyResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd: list[str], **kwargs) -> DummyResult:  # noqa: ANN001
        if cmd[:3] == ["op", "item", "create"] and "--format" in cmd:
            return DummyResult(returncode=1, stderr="You do not have permission")
        if cmd[:3] == ["op", "vault", "get"]:
            return DummyResult(returncode=0)
        return DummyResult(returncode=0)

    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/op")
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)

    def _fail_prompt(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("Prompt should not be called without write access.")

    monkeypatch.setattr(onboarding_cli, "_prompt_yes_no", _fail_prompt)
    monkeypatch.setattr(onboarding_cli.getpass, "getpass", lambda *_: "secret")
    monkeypatch.setattr(onboarding_cli.subprocess, "run", fake_run)

    assert (
        onboarding_cli._prompt_store_secret_in_1password(
            env_name="BRAVE_API_KEY",
            description="Brave Search API key",
            doc_hint=None,
        )
        is False
    )
    captured = capsys.readouterr().out
    assert "write access" in captured.lower()


def test_loads_brave_key_from_onepassword(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)
    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/op")

    def _load_secret(**_kwargs: object) -> str:
        return "brave-secret"

    monkeypatch.setattr(onboarding_cli, "_load_secret_from_1password", _load_secret)
    assert onboarding_cli._check_required_tool_secrets() is True
    captured = capsys.readouterr().out
    assert "Found BRAVE_API_KEY" in captured
