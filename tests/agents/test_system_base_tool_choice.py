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
from pydantic import BaseModel


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


class DummySystem5(SystemBase):
    def __init__(self) -> None:
        super().__init__(
            "System5/root",
            identity_prompt="test",
            responsibility_prompts=["test"],
        )

    def _get_systems_by_type(self, type: SystemType) -> list:  # noqa: A002
        return []


class DummyStructuredResponse(BaseModel):
    value: str


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
        _prompts: list[str], memory_context: list[str] | None = None
    ) -> None:
        _ = memory_context
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


@pytest.mark.asyncio
async def test_run_adds_output_contract_prompt_for_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = DummySystem()
    captured_prompts: list[str] = []

    async def fake_set_system_prompt(
        prompts: list[str], _memory_context: list[str] | None = None
    ) -> None:
        captured_prompts.extend(prompts)

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
            messages=[TextMessage(content='{"value":"ok"}', source="System4/root")]
        )
    )

    message = TextMessage(content="hello", source="User")
    context = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="structured_contract_test",
    )

    await system.run([message], context, output_content_type=DummyStructuredResponse)
    assert any("OUTPUT CONTRACT" in prompt for prompt in captured_prompts)
    assert any(
        "DummyStructuredResponse" in prompt or "value" in prompt
        for prompt in captured_prompts
    )


@pytest.mark.asyncio
async def test_run_retries_once_when_structured_output_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = DummySystem()

    async def fake_set_system_prompt(
        _prompts: list[str], memory_context: list[str] | None = None
    ) -> None:
        _ = memory_context
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
        side_effect=[
            TaskResult(
                messages=[TextMessage(content="not-json", source="System4/root")]
            ),
            TaskResult(
                messages=[TextMessage(content='{"value":"ok"}', source="System4/root")]
            ),
        ]
    )

    message = TextMessage(content="hello", source="User")
    context = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="structured_retry_test",
    )

    await system.run([message], context, output_content_type=DummyStructuredResponse)
    assert system._agent.run.await_count == 2
    second_call = system._agent.run.await_args_list[1]
    retry_messages = second_call.kwargs["task"]
    assert len(retry_messages) == 2
    assert "Return strict JSON" in retry_messages[-1].content


@pytest.mark.asyncio
async def test_run_falls_back_to_unstructured_when_json_generation_fails(
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
        side_effect=[
            RuntimeError("json_validate_failed: Failed to generate JSON"),
            TaskResult(
                messages=[TextMessage(content='{"value":"ok"}', source="System4/root")]
            ),
        ]
    )

    message = TextMessage(content="hello", source="User")
    context = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="structured_json_generation_fallback_test",
    )

    await system.run([message], context, output_content_type=DummyStructuredResponse)
    assert system._agent.run.await_count == 2
    second_call = system._agent.run.await_args_list[1]
    retry_messages = second_call.kwargs["task"]
    assert len(retry_messages) == 2
    assert "Return strict JSON only with this schema" in retry_messages[-1].content


@pytest.mark.asyncio
async def test_run_routes_unhandled_errors_to_team_system5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = DummySystem()
    system._publish_message_to_agent = AsyncMock()

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

    class _PolicySystem:
        def get_agent_id(self) -> AgentId:
            return AgentId.from_str("System5/root")

    monkeypatch.setattr(
        system, "_get_systems_by_type", lambda *_args: [_PolicySystem()]
    )
    system._agent.run = AsyncMock(side_effect=RuntimeError("boom"))

    message = TextMessage(content="hello", source="User")
    context = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="run_error_route_test",
    )

    from src.agents.system_base import InternalErrorRoutedError

    with pytest.raises(InternalErrorRoutedError):
        await system.run([message], context)

    system._publish_message_to_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_does_not_route_errors_for_system5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = DummySystem5()
    system._publish_message_to_agent = AsyncMock()

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
    system._agent.run = AsyncMock(side_effect=RuntimeError("boom"))

    message = TextMessage(content="hello", source="User")
    context = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="run_error_no_route_system5_test",
    )

    with pytest.raises(RuntimeError, match="boom"):
        await system.run([message], context)

    system._publish_message_to_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_bubbles_required_tool_choice_error_without_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = DummySystem()
    system._publish_message_to_agent = AsyncMock()

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
        side_effect=RuntimeError(
            "Tool choice is required, but model did not call a tool"
        )
    )

    message = TextMessage(content="hello", source="User")
    context = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="run_tool_choice_retry_test",
    )

    with pytest.raises(
        RuntimeError, match="Tool choice is required, but model did not call a tool"
    ):
        await system.run([message], context, tool_choice_required=True)

    system._publish_message_to_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_retries_on_messages_length_limit_without_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = DummySystem()
    system._publish_message_to_agent = AsyncMock()

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
        side_effect=[
            RuntimeError(
                "Error code: 400 - {'error': {'message': "
                "'Please reduce the length of the messages or completion.', "
                "'type': 'invalid_request_error', 'param': 'messages'}}"
            ),
            TaskResult(messages=[TextMessage(content="ok", source="System4/root")]),
        ]
    )

    monkeypatch.setenv("SYSTEM_CHAT_MESSAGE_MAX_CHARS", "80")
    message = TextMessage(content="X" * 200, source="User")
    context = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="run_messages_length_retry_test",
    )

    result = await system.run([message], context)
    assert result.messages[-1].to_text() == "ok"
    assert system._agent.run.await_count == 2
    second_call = system._agent.run.await_args_list[1]
    retry_messages = second_call.kwargs["task"]
    assert retry_messages[0].content.endswith("[truncated for message budget]")
    system._publish_message_to_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_system_prompt_compacts_when_budget_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = DummySystem()
    monkeypatch.setenv("SYSTEM_PROMPT_MAX_CHARS", "300")
    monkeypatch.setenv("SYSTEM_PROMPT_ENTRY_MAX_CHARS", "120")

    prompt = await system._set_system_prompt(
        message_specific_prompts=["A" * 600, "B" * 600],
        memory_context=["C" * 600],
    )

    assert len(prompt) <= 300
    assert SystemBase.MESSAGE_BUDGET_TRUNCATION_NOTE in prompt
