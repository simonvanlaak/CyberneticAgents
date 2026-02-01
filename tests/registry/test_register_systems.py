import pytest
from src.registry import register_systems
from src.cyberagent.core.runtime import get_runtime


@pytest.mark.asyncio
async def test_register_systems_idempotent():
    """Test that register_systems can be called multiple times without error."""
    # First registration - should succeed
    await register_systems()

    # Second registration - must be a no-op, not raise
    await register_systems()

    # Verify that the expected agents are present
    runtime = get_runtime()
    expected_agents = ["System1", "System3", "System4", "System5", "UserAgent"]

    for agent_name in expected_agents:
        assert (
            agent_name in runtime._known_agent_names
        ), f"Agent {agent_name} should be registered"
