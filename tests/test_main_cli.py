import pytest
from unittest.mock import AsyncMock

from autogen_core import AgentId

from main import CyberneticTUI, parse_cli_args, should_force_headless
from src.agents.messages import UserMessage


def test_parse_cli_args_none_when_missing():
    headless, message = parse_cli_args(["main.py"])
    assert headless is False
    assert message is None


def test_parse_cli_args_none_when_empty():
    headless, message = parse_cli_args(["main.py", "   "])
    assert headless is False
    assert message is None


def test_parse_cli_args_joins_args():
    headless, message = parse_cli_args(["main.py", "hello", "world"])
    assert headless is False
    assert message == "hello world"


def test_parse_cli_args_headless_flag():
    headless, message = parse_cli_args(["main.py", "--headless", "hello"])
    assert headless is True
    assert message == "hello"


def test_parse_cli_args_message_option():
    headless, message = parse_cli_args(["main.py", "--no-tui", "--message", "hi there"])
    assert headless is True
    assert message == "hi there"


def test_should_force_headless_when_not_tty(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert should_force_headless() is True

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    assert should_force_headless() is True

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert should_force_headless() is False


@pytest.mark.asyncio
async def test_cybernetic_tui_sends_initial_message_once():
    runtime = AsyncMock()
    recipient = AgentId.from_str("User/root")
    app = CyberneticTUI(runtime, recipient, initial_message="hello")

    await app._send_initial_message()

    runtime.send_message.assert_awaited_once()
    sent_message = runtime.send_message.call_args.kwargs["message"]
    assert isinstance(sent_message, UserMessage)
    assert sent_message.content == "hello"
    assert app._initial_message is None
