from typing import List
from unittest.mock import AsyncMock

import pytest
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, MessageContext
from autogen_core import CancellationToken
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from src.agents.system_base import SystemBase
from src.enums import SystemType


class DummySystem(SystemBase):
    def __init__(self) -> None:
        super().__init__(
            "System4/root",
            identity_prompt="test",
            responsibility_prompts=["test"],
        )

    def _get_systems_by_type(self, type: SystemType) -> List:  # noqa: A002
        return []


@pytest.mark.asyncio
async def test_run_propagates_traceparent(monkeypatch: pytest.MonkeyPatch) -> None:
    system = DummySystem()
    trace.set_tracer_provider(TracerProvider())

    async def fake_set_system_prompt(
        _prompts: List[str], _memory_context: List[str] | None = None
    ) -> None:
        return None

    monkeypatch.setattr(system, "_set_system_prompt", fake_set_system_prompt)
    monkeypatch.setattr(system, "_build_memory_context", lambda *_args: [])
    monkeypatch.setattr(
        "src.agents.system_base.mark_team_active", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "src.agents.system_base.get_model_client",
        lambda *_args, **_kwargs: object(),
    )

    system._agent.run = AsyncMock(
        return_value=TaskResult(
            messages=[TextMessage(content="ok", source="System4/root")]
        )
    )

    trace_id = "1" * 32
    span_id = "2" * 16
    message = TextMessage(
        content="hello",
        source="User",
        metadata={
            "trace_context": {"trace_id": trace_id, "span_id": span_id}.__repr__()
        },
    )

    context = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="trace_test",
    )

    result = await system.run([message], context)

    traceparent = result.messages[-1].metadata.get("traceparent")
    assert traceparent is not None
    assert traceparent.startswith(f"00-{trace_id}-")
