# -*- coding: utf-8 -*-
"""
Agent registration utilities for dynamic agent creation.
"""

from autogen_core import AgentInstantiationContext

from src.agents.system1 import System1
from src.agents.system3 import System3
from src.agents.system4 import System4
from src.agents.system5 import System5
from src.agents.user_agent import UserAgent
from src.cyberagent.core.runtime import get_runtime


async def register_systems() -> None:
    runtime = get_runtime()

    def factory_System1():
        agent_id = AgentInstantiationContext.current_agent_id()
        return System1(agent_id.key, None)

    def factory_System3():
        agent_id = AgentInstantiationContext.current_agent_id()
        return System3(agent_id.key, None)

    def factory_System4():
        agent_id = AgentInstantiationContext.current_agent_id()
        return System4(agent_id.key, None)

    def factory_System5():
        agent_id = AgentInstantiationContext.current_agent_id()
        return System5(agent_id.key, None)

    def factory_UserAgent():
        agent_id = AgentInstantiationContext.current_agent_id()
        return UserAgent(agent_id.key)

    if "System1" not in runtime._known_agent_names:
        await System1.register(runtime, "System1", factory_System1)
    if "System3" not in runtime._known_agent_names:
        await System3.register(runtime, "System3", factory_System3)
    if "System4" not in runtime._known_agent_names:
        await System4.register(runtime, "System4", factory_System4)
    if "System5" not in runtime._known_agent_names:
        await System5.register(runtime, "System5", factory_System5)
    if "UserAgent" not in runtime._known_agent_names:
        await UserAgent.register(runtime, "UserAgent", factory_UserAgent)
