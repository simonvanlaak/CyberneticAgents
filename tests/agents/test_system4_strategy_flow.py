import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, CancellationToken, MessageContext

from src.agents.messages import InitiativeAssignMessage, StrategyRequestMessage
from src.agents.system4 import InitiativeCreateResponse, StrategyCreateResponse, System4


@pytest.mark.asyncio
async def test_system4_strategy_request_triggers_system3_assignment(monkeypatch):
    system4 = System4("System4/root")
    system4.run = AsyncMock(
        return_value=TaskResult(messages=[TextMessage(content="ok", source="test")])
    )

    strategy_response = StrategyCreateResponse(
        name="Test Strategy",
        description="Test description",
        initiatives=[
            InitiativeCreateResponse(
                name="Initiative 1", description="First initiative"
            )
        ],
    )
    system4._get_structured_message = MagicMock(return_value=strategy_response)

    class DummyStrategy:
        def __init__(
            self, team_id: int, name: str, description: str, purpose_id=None, result=""
        ):
            self.team_id = team_id
            self.name = name
            self.description = description

        def add(self) -> int:
            return 1

        def get_initiatives(self):
            return []

        def to_prompt(self):
            return ["{}"]

    class DummyInitiative:
        def __init__(self, **kwargs):
            self.name = kwargs.get("name", "")
            self.description = kwargs.get("description", "")

        def add(self) -> None:
            return None

    monkeypatch.setattr("src.agents.system4.Strategy", DummyStrategy)
    monkeypatch.setattr("src.agents.system4.Initiative", DummyInitiative)
    monkeypatch.setattr(
        "src.agents.system4.get_or_create_default_purpose",
        lambda team_id: SimpleNamespace(id=1),
    )

    dummy_initiative = SimpleNamespace(
        name="Initiative 1",
        description="First initiative",
        get_assign_message=lambda: InitiativeAssignMessage(
            initiative_id=1, source="Initiative 1", content="Start initiative 1."
        ),
    )
    system4._select_next_initiative = AsyncMock(return_value=dummy_initiative)

    system3_agent = SimpleNamespace(
        get_agent_id=lambda: AgentId.from_str("System3/root")
    )
    monkeypatch.setattr(
        "src.agents.system4.get_system_by_type", lambda *args, **kwargs: system3_agent
    )

    system4._publish_message_to_agent = AsyncMock()

    ctx = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test",
    )
    message = StrategyRequestMessage(content="Create strategy", source="System5/root")

    await system4.handle_strategy_request_message(message, ctx)

    system4._publish_message_to_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_system4_strategy_request_includes_response_format(monkeypatch):
    system4 = System4("System4/root")
    captured: dict[str, object] = {}

    async def fake_run(
        messages, ctx, prompts, output_content_type=None
    ):  # noqa: ANN001
        captured["prompts"] = prompts
        return TaskResult(messages=[TextMessage(content="ok", source="test")])

    system4.run = fake_run
    system4._get_structured_message = MagicMock(
        return_value=StrategyCreateResponse(
            name="Test Strategy",
            description="Test description",
            initiatives=[
                InitiativeCreateResponse(
                    name="Initiative 1", description="First initiative"
                )
            ],
        )
    )

    class DummyStrategy:
        def __init__(
            self, team_id: int, name: str, description: str, purpose_id=None, result=""
        ):
            self.team_id = team_id
            self.name = name
            self.description = description

        def add(self) -> int:
            return 1

        def get_initiatives(self):
            return []

        def to_prompt(self):
            return ["{}"]

    class DummyInitiative:
        def __init__(self, **kwargs):
            self.name = kwargs.get("name", "")
            self.description = kwargs.get("description", "")

        def add(self) -> None:
            return None

    monkeypatch.setattr("src.agents.system4.Strategy", DummyStrategy)
    monkeypatch.setattr("src.agents.system4.Initiative", DummyInitiative)
    monkeypatch.setattr(
        "src.agents.system4.get_or_create_default_purpose",
        lambda team_id: SimpleNamespace(id=1),
    )
    dummy_initiative = SimpleNamespace(
        name="Initiative 1",
        description="First initiative",
        get_assign_message=lambda: InitiativeAssignMessage(
            initiative_id=1, source="Initiative 1", content="Start initiative 1."
        ),
    )
    system4._select_next_initiative = AsyncMock(return_value=dummy_initiative)
    system4._publish_message_to_agent = AsyncMock()

    ctx = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test",
    )
    message = StrategyRequestMessage(content="Create strategy", source="System5/root")

    await system4.handle_strategy_request_message(message, ctx)

    prompts = captured.get("prompts", [])
    assert "## RESPONSE FORMAT" in prompts
    assert "Only return valid JSON with these fields." in prompts


@pytest.mark.asyncio
async def test_system4_strategy_request_falls_back_to_first_initiative(monkeypatch):
    system4 = System4("System4/root")
    system4.run = AsyncMock(
        return_value=TaskResult(messages=[TextMessage(content="ok", source="test")])
    )

    strategy_response = StrategyCreateResponse(
        name="Test Strategy",
        description="Test description",
        initiatives=[
            InitiativeCreateResponse(
                name="Initiative 1", description="First initiative"
            ),
            InitiativeCreateResponse(
                name="Initiative 2", description="Second initiative"
            ),
        ],
    )
    system4._get_structured_message = MagicMock(return_value=strategy_response)

    class DummyStrategy:
        def __init__(
            self, team_id: int, name: str, description: str, purpose_id=None, result=""
        ):
            self.team_id = team_id
            self.name = name
            self.description = description

        def add(self) -> int:
            return 1

        def get_initiatives(self):
            return []

        def to_prompt(self):
            return ["{}"]

    class DummyInitiative:
        def __init__(self, **kwargs):
            self.id = kwargs.get("id", 1)
            self.name = kwargs.get("name", "")
            self.description = kwargs.get("description", "")

        def add(self) -> None:
            return None

        def get_assign_message(self):
            return InitiativeAssignMessage(
                initiative_id=1, source=self.name, content="Start initiative 1."
            )

    monkeypatch.setattr("src.agents.system4.Strategy", DummyStrategy)
    monkeypatch.setattr("src.agents.system4.Initiative", DummyInitiative)
    monkeypatch.setattr(
        "src.agents.system4.get_or_create_default_purpose",
        lambda team_id: SimpleNamespace(id=1),
    )

    system4._select_next_initiative = AsyncMock(side_effect=ValueError("fail"))

    system3_agent = SimpleNamespace(
        get_agent_id=lambda: AgentId.from_str("System3/root")
    )
    monkeypatch.setattr(
        "src.agents.system4.get_system_by_type", lambda *args, **kwargs: system3_agent
    )

    system4._publish_message_to_agent = AsyncMock()

    ctx = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="test",
    )
    message = StrategyRequestMessage(content="Create strategy", source="System5/root")

    await system4.handle_strategy_request_message(message, ctx)

    system4._publish_message_to_agent.assert_awaited_once()
