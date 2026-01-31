from src.ui_state import (
    add_message,
    add_user_notice,
    clear_messages,
    get_latest_user_notice,
    set_log_file,
)


def test_get_latest_user_notice_returns_last_notice():
    clear_messages()
    add_message(sender="System4", content="log entry", is_user=False)
    assert get_latest_user_notice() is None

    add_user_notice(sender="System4", content="First update")
    add_user_notice(sender="System4", content="Second update")

    notice = get_latest_user_notice()
    assert notice is not None
    assert notice.content == "Second update"


def test_set_log_file_appends_messages(tmp_path):
    log_path = tmp_path / "chat.log"
    set_log_file(str(log_path))
    clear_messages()

    add_message(sender="User", content="Hello", is_user=True)
    add_user_notice(sender="System4", content="Update")

    data = log_path.read_text(encoding="utf-8")
    assert "MESSAGE [User] Hello" in data
    assert "NOTICE [System4] Update" in data


def test_internal_messages_are_not_logged(tmp_path):
    log_path = tmp_path / "chat.log"
    set_log_file(str(log_path))
    clear_messages()

    add_message(sender="System4", content="...[System4] internal", is_user=False)

    assert log_path.exists() is False


def test_get_latest_user_notice_skips_empty():
    clear_messages()
    add_user_notice(sender="System4", content="First update")
    add_user_notice(sender="System4", content="   ")

    notice = get_latest_user_notice()
    assert notice is not None
    assert notice.content == "First update"
