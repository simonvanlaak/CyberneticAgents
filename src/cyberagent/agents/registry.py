# -*- coding: utf-8 -*-
"""
Agent registration utilities for dynamic agent creation.
"""

from autogen_core import AgentInstantiationContext

from src.cyberagent.agents.system1 import System1
from src.cyberagent.agents.system3 import System3
from src.cyberagent.agents.system4 import System4
from src.cyberagent.agents.system5 import System5
from src.cyberagent.agents.user_agent import UserAgent
from src.cyberagent.core.agent_registration import is_registered, mark_registered
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

    if not is_registered(runtime, "System1"):
        await System1.register(runtime, "System1", factory_System1)
        mark_registered(runtime, "System1")
    if not is_registered(runtime, "System3"):
        await System3.register(runtime, "System3", factory_System3)
        mark_registered(runtime, "System3")
    if not is_registered(runtime, "System4"):
        await System4.register(runtime, "System4", factory_System4)
        mark_registered(runtime, "System4")
    if not is_registered(runtime, "System5"):
        await System5.register(runtime, "System5", factory_System5)
        mark_registered(runtime, "System5")
    if not is_registered(runtime, "UserAgent"):
        await UserAgent.register(runtime, "UserAgent", factory_UserAgent)
        mark_registered(runtime, "UserAgent")
