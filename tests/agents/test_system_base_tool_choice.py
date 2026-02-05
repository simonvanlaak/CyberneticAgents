from __future__ import annotations

from typing import Any, Sequence
from unittest.mock import AsyncMock

import pytest
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, CancellationToken, MessageContext
from autogen_core.models import (
    ChatCompletionClient,
    CreateResult,
    ModelCapabilities,
    ModelInfo,
    RequestUsage,
)
from autogen_core.tools import Tool, ToolSchema

from src.agents.system_base import ToolChoiceRequiredClient, SystemBase
from src.enums import SystemType


class DummyModelClient(ChatCompletionClient):
    def __init__(self) -> None:
        self.last_tool_choice: Tool | str | None = None
        self._model_info: ModelInfo = {
            "vision": False,
            "function_calling": True,
            "json_output": False,
            "family": "test",
            "structured_output": False,
        }
        self._capabilities: ModelCapabilities = {
            "vision": False,
            "function_calling": True,
            "json_output": False,
        }

    async def create(
        self,
        messages: Sequence[Any],
        *,
        tools: Sequence[Tool | ToolSchema] = (),
        tool_choice: Tool | str = "auto",
        json_output=None,
        extra_create_args=None,
        cancellation_token=None,
    ) -> CreateResult:
        self.last_tool_choice = tool_choice
        return CreateResult(
            finish_reason="stop",
            content="ok",
            usage=RequestUsage(prompt_tokens=0, completion_tokens=0),
            cached=False,
        )

    def create_stream(self, *args: Any, **kwargs: Any):  # noqa: ANN001
        raise AssertionError("Not used in this test.")

    async def close(self) -> None:
        return None

    def actual_usage(self) -> RequestUsage:
        return RequestUsage(prompt_tokens=0, completion_tokens=0)

    def total_usage(self) -> RequestUsage:
        return RequestUsage(prompt_tokens=0, completion_tokens=0)

    def count_tokens(self, messages: Sequence[Any], *, tools=()) -> int:  # noqa: ANN001
        return 0

    def remaining_tokens(
        self, messages: Sequence[Any], *, tools=()  # noqa: ANN001
    ) -> int:
        return 0

    @property
    def capabilities(self) -> ModelCapabilities:  # type: ignore[override]
        return self._capabilities

    @property
    def model_info(self) -> ModelInfo:  # type: ignore[override]
        return self._model_info


class DummySystem(SystemBase):
    def __init__(self) -> None:
        super().__init__(
            "System4/root",
            identity_prompt="test",
            responsibility_prompts=["test"],
        )

    def _get_systems_by_type(self, type: SystemType) -> list:  # noqa: A002
        return []


@pytest.mark.asyncio
async def test_tool_choice_required_client_forces_required() -> None:
    client = DummyModelClient()
    wrapper = ToolChoiceRequiredClient(client)
    await wrapper.create([])
    assert client.last_tool_choice == "required"


@pytest.mark.asyncio
async def test_run_wraps_model_client_when_tool_choice_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = DummySystem()

    async def fake_set_system_prompt(
        _prompts: list[str], _memory_context: list[str] | None = None
    ) -> None:
        return None

    monkeypatch.setattr(system, "_set_system_prompt", fake_set_system_prompt)
    monkeypatch.setattr(system, "_build_memory_context", lambda *_args: [])
    monkeypatch.setattr(
        "src.agents.system_base.mark_team_active", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "src.agents.system_base.get_model_client",
        lambda *_args, **_kwargs: DummyModelClient(),
    )
    system._agent.run = AsyncMock(
        return_value=TaskResult(
            messages=[TextMessage(content="ok", source="System4/root")]
        )
    )

    message = TextMessage(content="hello", source="User")
    context = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="tool_choice_test",
    )

    await system.run([message], context, tool_choice_required=True)
    assert isinstance(system._agent._model_client, ToolChoiceRequiredClient)
