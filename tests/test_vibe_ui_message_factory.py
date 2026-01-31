from src.ui.vibe_ui.app import create_message_widget
from src.ui.vibe_ui.widgets.messages import AssistantMessage, UserMessage
from src.ui_state import UiMessage


def test_create_message_widget_user() -> None:
    message = UiMessage(
        sender="User",
        content="hello",
        is_user=True,
        timestamp=0.0,
    )

    widget = create_message_widget(message)

    assert isinstance(widget, UserMessage)
    assert widget._content == "hello"


def test_create_message_widget_assistant() -> None:
    message = UiMessage(
        sender="System",
        content="hi there",
        is_user=False,
        timestamp=0.0,
    )

    widget = create_message_widget(message)

    assert isinstance(widget, AssistantMessage)
    assert widget._content == "hi there"
