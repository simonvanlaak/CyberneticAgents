from __future__ import annotations

import argparse
import os

import pytest

from src.cyberagent.cli import cyberagent
from sqlalchemy.exc import SQLAlchemyError

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.cli import onboarding_interview
from src.cyberagent.cli import onboarding_telegram
from src.cyberagent.channels.telegram import session_store
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team

ONBOARDING = getattr(cyberagent, "onboarding_cli", cyberagent)


def _handle_onboarding(args: argparse.Namespace) -> int:
    handle_onboarding = getattr(ONBOARDING, "handle_onboarding", None)
    if handle_onboarding is not None:
        return handle_onboarding(
            args, cyberagent.SUGGEST_COMMAND, cyberagent.INBOX_COMMAND
        )
    return ONBOARDING._handle_onboarding(args)


def _patch_run_checks(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    run_checks = getattr(ONBOARDING, "run_technical_onboarding_checks", None)
    if run_checks is None:
        monkeypatch.setattr(
            ONBOARDING, "_run_technical_onboarding_checks", lambda: value
        )
        return
    monkeypatch.setattr(ONBOARDING, "run_technical_onboarding_checks", lambda: value)


def _clear_teams() -> None:
    session = next(get_db())
    try:
        session.query(System).delete()
        session.query(Team).delete()
        session.commit()
    finally:
        session.close()


def _default_onboarding_args() -> argparse.Namespace:
    return argparse.Namespace(
        user_name="Test User",
        repo_url="https://github.com/example/repo",
        profile_links=["https://example.com/profile"],
        token_env="GITHUB_READONLY_TOKEN",
        token_username="x-access-token",
    )


def test_handle_onboarding_creates_default_team(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_teams()
    _patch_run_checks(monkeypatch, True)
    called: dict[str, bool] = {}
    monkeypatch.setattr(
        ONBOARDING,
        "_start_discovery_background",
        lambda *_args, **_kwargs: called.setdefault("background", True),
    )
    monkeypatch.setattr(
        ONBOARDING,
        "start_onboarding_interview",
        lambda *_args, **_kwargs: called.setdefault("interview", True),
    )
    monkeypatch.setattr(
        ONBOARDING, "_trigger_onboarding_initiative", lambda *_, **__: True
    )
    monkeypatch.setattr(
        ONBOARDING,
        "_run_discovery_onboarding",
        lambda *_args, **_kwargs: "data/onboarding/summary.md",
    )

    exit_code = _handle_onboarding(_default_onboarding_args())
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "Created default team" in captured
    assert "Starting PKM sync and profile discovery" in captured
    assert called.get("background") is None
    assert called.get("interview") is True

    expected_name = (
        "root" if hasattr(ONBOARDING, "handle_onboarding") else "default_team"
    )
    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == expected_name).first()
        assert team is not None
    finally:
        session.close()


def test_handle_onboarding_skips_when_team_exists(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_teams()
    session = next(get_db())
    try:
        session.add(Team(name="existing_team"))
        session.commit()
    finally:
        session.close()

    _patch_run_checks(monkeypatch, True)
    called: dict[str, bool] = {}
    monkeypatch.setattr(
        ONBOARDING,
        "_start_discovery_background",
        lambda *_args, **_kwargs: called.setdefault("background", True),
    )
    monkeypatch.setattr(
        ONBOARDING,
        "start_onboarding_interview",
        lambda *_args, **_kwargs: called.setdefault("interview", True),
    )
    monkeypatch.setattr(
        ONBOARDING, "_trigger_onboarding_initiative", lambda *_, **__: True
    )
    monkeypatch.setattr(
        ONBOARDING,
        "_run_discovery_onboarding",
        lambda *_args, **_kwargs: "data/onboarding/summary.md",
    )

    exit_code = _handle_onboarding(_default_onboarding_args())
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "Team already exists" in captured
    assert "Starting PKM sync and profile discovery" in captured
    assert called.get("background") is None
    assert called.get("interview") is True

    session = next(get_db())
    try:
        assert session.query(Team).count() == 1
    finally:
        session.close()


def test_handle_onboarding_requires_technical_checks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()

    _patch_run_checks(monkeypatch, False)

    exit_code = _handle_onboarding(_default_onboarding_args())
    captured = capsys.readouterr().out

    assert exit_code == 1
    assert "technical onboarding" in captured.lower()


def test_select_latest_telegram_session_picks_most_recent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    older = session_store.TelegramSession(
        telegram_user_id=1,
        telegram_chat_id=10,
        agent_session_id="telegram:chat-10:user-1",
        user_info={},
        chat_type="private",
        created_at=1.0,
        last_activity=2.0,
    )
    newer = session_store.TelegramSession(
        telegram_user_id=2,
        telegram_chat_id=20,
        agent_session_id="telegram:chat-20:user-2",
        user_info={},
        chat_type="private",
        created_at=1.0,
        last_activity=5.0,
    )

    monkeypatch.setattr(onboarding_interview, "session_store", session_store)
    monkeypatch.setattr(
        onboarding_interview.session_store, "list_sessions", lambda: [older, newer]
    )

    selected = onboarding_interview.select_latest_telegram_session()

    assert selected is newer


def test_send_onboarding_intro_messages_sends_two_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = session_store.TelegramSession(
        telegram_user_id=2,
        telegram_chat_id=20,
        agent_session_id="telegram:chat-20:user-2",
        user_info={},
        chat_type="private",
        created_at=1.0,
        last_activity=5.0,
    )
    sent: list[tuple[int, str]] = []

    def _fake_send(chat_id: int, text: str) -> None:
        sent.append((chat_id, text))

    monkeypatch.setattr(onboarding_interview, "session_store", session_store)
    monkeypatch.setattr(
        onboarding_interview.session_store, "list_sessions", lambda: [session]
    )
    monkeypatch.setattr(onboarding_interview, "get_secret", lambda *_args: "token")
    monkeypatch.setattr(onboarding_interview, "send_telegram_message", _fake_send)
    monkeypatch.setattr(
        onboarding_interview,
        "get_message",
        lambda *_args, **_kwargs: "Send message to bot.",
    )

    used, session_found = onboarding_interview.send_onboarding_intro_messages(
        welcome_message="Welcome!",
        first_question="First question?",
    )

    assert used is True
    assert session_found is True
    assert sent == [(20, "Welcome!"), (20, "First question?")]


def test_start_onboarding_interview_prints_telegram_session_hint(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_secret(name: str) -> str | None:
        if name == "TELEGRAM_BOT_TOKEN":
            return "token"
        if name == "TELEGRAM_BOT_USERNAME":
            return "mybot"
        return None

    monkeypatch.setattr(onboarding_interview, "get_secret", _fake_secret)
    monkeypatch.setattr(
        onboarding_interview,
        "send_onboarding_intro_messages",
        lambda **_kwargs: (True, True),
    )
    monkeypatch.setattr(
        onboarding_interview,
        "get_message",
        lambda *_args, **_kwargs: "Send message to bot.",
    )
    monkeypatch.setattr(onboarding_interview, "enqueue_suggestion", lambda *_: None)
    monkeypatch.setattr(
        onboarding_interview,
        "build_onboarding_interview_prompt",
        lambda **_kwargs: "prompt",
    )
    monkeypatch.setattr(
        onboarding_interview, "build_bot_link", lambda: "https://t.me/mybot"
    )
    monkeypatch.setattr(onboarding_interview, "render_telegram_qr", lambda *_: "QR")

    onboarding_interview.start_onboarding_interview(
        user_name="Simon",
        repo_url="https://example.com/repo",
        profile_links=[],
    )

    captured = capsys.readouterr().out
    assert "Send message to bot." in captured
    assert "t.me/mybot" in captured
    assert "QR" in captured


def test_start_onboarding_interview_fetches_bot_username_when_missing(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_secret(name: str) -> str | None:
        if name == "TELEGRAM_BOT_TOKEN":
            return "token"
        if name == "TELEGRAM_BOT_USERNAME":
            return None
        return None

    monkeypatch.setattr(onboarding_interview, "get_secret", _fake_secret)
    monkeypatch.setattr(
        onboarding_interview,
        "send_onboarding_intro_messages",
        lambda **_kwargs: (True, True),
    )
    monkeypatch.setattr(
        onboarding_interview,
        "get_message",
        lambda *_args, **_kwargs: "Send message to bot.",
    )
    monkeypatch.setattr(onboarding_interview, "enqueue_suggestion", lambda *_: None)
    monkeypatch.setattr(
        onboarding_interview,
        "build_onboarding_interview_prompt",
        lambda **_kwargs: "prompt",
    )
    build_calls = 0

    def _fake_build_bot_link() -> str | None:
        nonlocal build_calls
        build_calls += 1
        if build_calls == 1:
            return None
        return "https://t.me/mybot"

    monkeypatch.setattr(onboarding_interview, "build_bot_link", _fake_build_bot_link)
    monkeypatch.setattr(
        onboarding_interview.onboarding_telegram,
        "_fetch_bot_username_from_token",
        lambda *_: "mybot",
    )
    monkeypatch.setattr(onboarding_interview, "render_telegram_qr", lambda *_: "QR")

    onboarding_interview.start_onboarding_interview(
        user_name="Simon",
        repo_url="https://example.com/repo",
        profile_links=[],
    )

    captured = capsys.readouterr().out
    assert "Send message to bot." in captured
    assert "t.me/mybot" in captured
    assert "QR" in captured


def test_send_onboarding_intro_messages_no_session_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(onboarding_interview, "session_store", session_store)
    monkeypatch.setattr(onboarding_interview, "get_secret", lambda *_args: "token")
    monkeypatch.setattr(onboarding_interview.session_store, "list_sessions", lambda: [])
    monkeypatch.setattr(
        onboarding_interview,
        "get_message",
        lambda *_args, **_kwargs: "Send message to bot.",
    )

    used, session_found = onboarding_interview.send_onboarding_intro_messages(
        welcome_message="Welcome!",
        first_question="First question?",
    )

    assert used is False
    assert session_found is False


def test_print_db_write_error_attempts_recovery(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(onboarding_cli, "get_database_path", lambda: "data/test.db")
    monkeypatch.setattr(onboarding_cli, "recover_sqlite_database", lambda: "backup.db")
    monkeypatch.setattr(
        onboarding_cli,
        "get_message",
        lambda _group, key, **kwargs: (
            f"Recovered {kwargs['backup_path']}"
            if key == "db_recovered_hint"
            else "hint"
        ),
    )

    onboarding_cli._print_db_write_error(
        "procedure run", SQLAlchemyError("disk I/O error")
    )

    captured = capsys.readouterr().out
    assert "Recovered backup.db" in captured


def test_offer_optional_telegram_setup_sets_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(onboarding_telegram.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(
        onboarding_telegram, "_load_secret_from_1password", lambda *_: "tok"
    )
    monkeypatch.setattr(
        onboarding_telegram, "_fetch_bot_username_from_token", lambda *_: None
    )
    monkeypatch.setattr(
        onboarding_telegram, "_offer_optional_telegram_webhook_setup", lambda: None
    )
    monkeypatch.setattr(onboarding_cli, "_print_feature_ready", lambda *_: None)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    onboarding_telegram.offer_optional_telegram_setup()

    assert os.environ.get("TELEGRAM_BOT_TOKEN") == "tok"


def test_offer_optional_telegram_setup_autofills_username_from_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(onboarding_telegram.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(
        onboarding_telegram, "_load_secret_from_1password", lambda *_: None
    )
    monkeypatch.setattr(
        onboarding_telegram, "_fetch_bot_username_from_token", lambda *_: "mybot"
    )
    monkeypatch.setattr(
        onboarding_telegram, "_offer_optional_telegram_webhook_setup", lambda: None
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.delenv("TELEGRAM_BOT_USERNAME", raising=False)

    def _fail_store(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("Should not prompt for username when fetched via API.")

    monkeypatch.setattr(
        onboarding_telegram, "prompt_store_secret_in_1password", _fail_store
    )

    onboarding_telegram.offer_optional_telegram_setup()

    assert os.environ.get("TELEGRAM_BOT_USERNAME") == "mybot"
