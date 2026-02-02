# System4 Agent Tests - Sequential Processing
# Tests for System4 (Intelligence) agent with sequential processing

import pytest
from unittest.mock import AsyncMock
import src.agents.system4 as system4_module
from autogen_core import AgentId

from src.agents.system4 import (
    InitiativeAdjustResponse,
    InitiativeCreateResponse,
    ResearchResultsResponse,
    StrategyAdjustResponse,
    StrategyCreateResponse,
    System4,
)
from src.agents.messages import (
    StrategyRequestMessage,
    InitiativeReviewMessage,
    ResearchRequestMessage,
    UserMessage,
)


class TestSystem4SequentialProcessing:
    """Test System4 sequential processing functionality."""

    def test_system4_creation(self):
        """Test System4 creation with proper AutoGen format."""
        system4 = System4("System4/intelligence1")
        assert system4 is not None
        assert system4.agent_id.type == "System4"
        assert system4.agent_id.key == "intelligence1"

    def test_system4_tools_available(self):
        """Test that System4 has the required tools available."""
        system4 = System4("System4/intelligence1")

        # Check that tools are available
        tool_names = [tool.name for tool in system4.tools]
        assert "ContactUserTool" in tool_names
        assert "InformUserTool" in tool_names
        assert "suggest_policy_tool" in tool_names

    def test_system4_sequential_processing_logic(self):
        """Test the sequential processing logic for System4."""
        system4 = System4("System4/intelligence1")

        # Mock the run method to simulate different scenarios
        system4.run = AsyncMock()

        # Test that tools can be temporarily removed
        original_tools = system4.tools.copy()
        system4.tools = []
        assert len(system4.tools) == 0

        # Restore tools
        system4.tools = original_tools
        assert len(system4.tools) == len(original_tools)


class TestSystem4StructuredResponses:
    """Test System4 structured response types."""

    def test_strategy_create_response(self):
        """Test StrategyCreateResponse structure."""
        initiative_response = InitiativeCreateResponse(
            name="Initiative 1", description="Description 1"
        )

        response = StrategyCreateResponse(
            name="Test Strategy",
            description="Strategy description",
            initiatives=[initiative_response],
        )

        assert response.name == "Test Strategy"
        assert response.description == "Strategy description"
        assert len(response.initiatives) == 1

    def test_strategy_adjust_response(self):
        """Test StrategyAdjustResponse structure."""
        initiative_adjust = InitiativeAdjustResponse(
            id=1, name="Updated Initiative", description="Updated description"
        )

        response = StrategyAdjustResponse(
            name="Updated Strategy",
            description="Updated description",
            initiatives=[initiative_adjust],
        )

        assert response.name == "Updated Strategy"
        assert response.description == "Updated description"
        assert len(response.initiatives) == 1

    def test_research_results_response(self):
        """Test ResearchResultsResponse structure."""
        response = ResearchResultsResponse(
            findings="Research findings",
            sources=["Source 1", "Source 2"],
            recommendations=["Recommendation 1", "Recommendation 2"],
        )

        assert response.findings == "Research findings"
        assert len(response.sources) == 2
        assert len(response.recommendations) == 2


class TestSystem4MessageHandling:
    """Test System4 message handling."""

    def test_strategy_request_message(self):
        """Test StrategyRequestMessage creation."""
        message = StrategyRequestMessage(
            content="Create strategy for X", source="System5/policy1"
        )
        assert message.content == "Create strategy for X"
        assert message.source == "System5/policy1"

    def test_initiative_review_message(self):
        """Test InitiativeReviewMessage creation."""
        message = InitiativeReviewMessage(
            initiative_id=1, content="Review request", source="System3/control1"
        )
        assert message.initiative_id == 1
        assert message.source == "System3/control1"
        # Confirm it does NOT have initiative object (similar to System3 issue)
        assert not hasattr(message, "initiative")

    def test_research_request_message(self):
        """Test ResearchRequestMessage creation."""
        message = ResearchRequestMessage(
            content="Research topic X", source="System5/policy1"
        )
        assert message.content == "Research topic X"
        assert message.source == "System5/policy1"

    def test_user_message(self):
        """Test UserMessage creation."""
        message = UserMessage(content="User question", source="User")
        assert message.content == "User question"
        assert message.source == "User"


@pytest.mark.asyncio
async def test_suggest_policy_tool_omits_missing_policy(
    monkeypatch: pytest.MonkeyPatch,
):
    system4 = System4("System4/root")
    captured: dict[str, object] = {}

    async def fake_publish(message, _agent_id):  # noqa: ANN001
        captured["message"] = message

    monkeypatch.setattr(system4, "_publish_message_to_agent", fake_publish)
    monkeypatch.setattr(
        system4_module.policy_service, "get_policy_by_id", lambda _pid: None
    )

    class DummySystem:
        def get_agent_id(self):
            return AgentId.from_str("System5/root")

    monkeypatch.setattr(
        "src.agents.system4.get_system_by_type", lambda *_: DummySystem()
    )

    await system4.suggest_policy_tool(123, "Test suggestion")

    message = captured.get("message")
    assert message is not None
    assert message.policy_id is None


class TestSystem4Integration:
    """Test System4 integration scenarios."""

    def test_system4_with_trace_context(self):
        """Test System4 with trace context."""
        trace_context = {"trace_id": "abc123", "span_id": "def456"}
        system4 = System4("System4/intelligence1", trace_context=trace_context)
        assert system4.trace_context == trace_context


@pytest.mark.asyncio
async def test_system4_sequential_processing_demo():
    """Demonstrate the sequential processing implementation for System4."""
    system4 = System4("System4/intelligence1")

    print(f"System4 created: {system4.name}")
    print(f"Available tools: {[tool.name for tool in system4.tools]}")

    # Test the sequential processing concept
    print("\n=== System4 Sequential Processing ===")
    print("Methods that need sequential processing:")
    print("1. handle_strategy_request_message - StrategyCreateResponse + tools")
    print("2. handle_initiative_review_message - StrategyAdjustResponse + tools")
    print("3. handle_research_request_message - ResearchResultsResponse + tools")
    print("4. handle_user_message - AssistantMessage + tools")

    # Test message creation
    strategy_message = StrategyRequestMessage(
        content="Create strategy for expansion", source="System5/policy1"
    )

    print(f"\nStrategy request: {strategy_message.content}")

    user_message = UserMessage(content="What is the current status?", source="User")

    print(f"User message: {user_message.content}")

    print("\nSystem4 sequential processing implementation test completed!")


if __name__ == "__main__":
    # Run basic test
    import asyncio

    asyncio.run(test_system4_sequential_processing_demo())
