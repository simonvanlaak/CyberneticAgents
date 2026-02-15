from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import src.cyberagent.agents.registry as registry
from src.cyberagent.core.agent_registration import reset_for_tests


@pytest.mark.asyncio
async def test_cyberagent_register_systems_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling canonical register_systems repeatedly should not register twice."""
    reset_for_tests()
    runtime = object()
    monkeypatch.setattr(registry, "get_runtime", lambda: runtime)

    register_system1 = AsyncMock()
    register_system3 = AsyncMock()
    register_system4 = AsyncMock()
    register_system5 = AsyncMock()
    register_user_agent = AsyncMock()

    monkeypatch.setattr(registry.System1, "register", register_system1)
    monkeypatch.setattr(registry.System3, "register", register_system3)
    monkeypatch.setattr(registry.System4, "register", register_system4)
    monkeypatch.setattr(registry.System5, "register", register_system5)
    monkeypatch.setattr(registry.UserAgent, "register", register_user_agent)

    await registry.register_systems()
    await registry.register_systems()

    assert register_system1.await_count == 1
    assert register_system3.await_count == 1
    assert register_system4.await_count == 1
    assert register_system5.await_count == 1
    assert register_user_agent.await_count == 1
