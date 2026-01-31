"""Vibe-inspired TUI adapted for CyberneticAgents.

Derived from Mistral Vibe (Apache 2.0). See third_party/mistral-vibe/LICENSE.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from autogen_core import AgentId
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Input, Static, TextArea

from src.agents.messages import UserMessage
from src.cli_session import MessageRuntime, get_pending_question
from src.ui_state import UiMessage, get_latest_user_notice, get_log_text, get_messages
from src.ui.vibe_ui.widgets.messages import (
    AssistantMessage,
    UserMessage as VibeUserMessage,
)
from src.ui.vibe_ui.widgets.no_markup_static import NoMarkupStatic
from src.ui.vibe_ui.widgets.path_display import PathDisplay


def create_message_widget(message: UiMessage) -> Widget:
    """Create a Vibe-style widget for a UI message."""
    if message.is_user:
        return VibeUserMessage(message.content)
    return AssistantMessage(message.content)


class CyberneticTUI(App):
    """Textual TUI that reuses Vibe's layout and message components."""

    BINDINGS = [("l", "toggle_log_view", "Logs")]
    CSS_PATH = "app.tcss"

    def __init__(
        self,
        runtime: MessageRuntime,
        recipient: AgentId,
        initial_message: str | None = None,
    ) -> None:
        super().__init__()
        self.runtime = runtime
        self.recipient = recipient
        self._last_message_index = 0
        self._initial_message = initial_message
        self._auto_scroll = True

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chat"):
            yield Static(id="messages")

        yield Static(id="todo-area")

        with Static(id="bottom-app-container"):
            with Horizontal(id="input-box"):
                yield NoMarkupStatic("> ", id="prompt")
                yield Input(placeholder="Ask anything...", id="input")

        with Horizontal(id="bottom-bar"):
            yield PathDisplay(Path.cwd())
            yield NoMarkupStatic(id="spacer")

    def on_mount(self) -> None:
        self.set_interval(0.25, self.refresh_ui)
        self.refresh_ui()
        if self._initial_message:
            asyncio.create_task(self._send_initial_message())

    def refresh_ui(self) -> None:
        self._refresh_pending_question()
        self._refresh_messages()

    def _refresh_pending_question(self) -> None:
        pending = get_pending_question()
        notice = get_latest_user_notice()
        if notice and notice.content.strip():
            notice_text = f"Latest update:\n[{notice.sender}] {notice.content}"
        else:
            notice_text = ""
        pending_text = (
            f"Pending question:\n{pending.content}" if pending else "No pending questions."
        )
        if notice_text and pending:
            display_text = f"{notice_text}\n\n{pending_text}"
        elif notice_text:
            display_text = notice_text
        else:
            display_text = pending_text
        self.query_one("#todo-area", Static).update(display_text)

    def _refresh_messages(self) -> None:
        messages = get_messages()
        if self._last_message_index >= len(messages):
            return
        container = self.query_one("#messages", Static)
        for msg in messages[self._last_message_index :]:
            container.mount(create_message_widget(msg))
        self._last_message_index = len(messages)
        if self._auto_scroll:
            self.query_one("#chat", VerticalScroll).scroll_end(animate=False)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        if text.lower() in {"/exit", "/quit"}:
            self.exit()
            return
        await self.runtime.send_message(
            message=UserMessage(content=text, source="User"),
            recipient=self.recipient,
        )
        event.input.value = ""

    async def _send_initial_message(self) -> None:
        if not self._initial_message:
            return
        text = self._initial_message.strip()
        self._initial_message = None
        if not text:
            return
        await self.runtime.send_message(
            message=UserMessage(content=text, source="User"),
            recipient=self.recipient,
        )

    def action_toggle_log_view(self) -> None:
        if self.screen.id == "log_view":
            self.pop_screen()
        else:
            self.push_screen(LogView())


class LogView(Screen):
    def __init__(self) -> None:
        super().__init__(id="log_view")

    def compose(self) -> ComposeResult:
        yield TextArea(get_log_text(), id="log_view", read_only=True)

    def on_mount(self) -> None:
        textarea = self.query_one("#log_view", TextArea)
        textarea.text = get_log_text()
