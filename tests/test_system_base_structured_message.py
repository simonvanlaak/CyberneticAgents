from typing import List
from unittest.mock import MagicMock
import sys

from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import StructuredMessage
from pydantic import BaseModel

sys.modules.setdefault("langfuse", MagicMock())

from src.agents.system_base import SystemBase  # noqa: E402


class DummySystem(SystemBase):
    def __init__(self) -> None:
        super().__init__(
            "System4/root",
            identity_prompt="test",
            responsibility_prompts=["test"],
        )

    def _get_systems_by_type(self, type: int) -> List:
        return []


def test_get_structured_message_returns_typed_content():
    system = DummySystem()

    class DummyContent(BaseModel):
        name: str
        description: str

    content = DummyContent(name="Test Strategy", description="Desc")
    message = StructuredMessage[DummyContent](
        content=content,
        source="System4/root",
    )
    result = TaskResult(messages=[message])

    parsed = system._get_structured_message(result, DummyContent)

    assert parsed == content
