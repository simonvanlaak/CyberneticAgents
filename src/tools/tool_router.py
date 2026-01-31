from typing import List

from autogen_core import AgentId
from autogen_core.tools import BaseTool

from src.rbac.enforcer import get_tools_names
from src.tools.delegate import Delegate
from src.tools.escalate import Escalate
from src.tools.policy_management import PolicyManagement
from src.tools.system_create import SystemCreate
from src.tools.system_evolve import SystemEvolve
from src.tools.system_list import SystemList
from src.tools.system_read import SystemRead

ALL_TOOLS = [
    Delegate,
    Escalate,
    PolicyManagement,
    SystemCreate,
    SystemEvolve,
    SystemList,
    SystemRead,
]


def get_tools(agent_id: AgentId) -> List[BaseTool]:
    """Get tools for agent with namespace support."""
    tool_names = get_tools_names(str(agent_id))
    tools = []
    for tool_class in ALL_TOOLS:
        if tool_class.__name__ in tool_names:
            # Instantiate the tool with the agent_id
            tool_instance = tool_class(agent_id)
            tools.append(tool_instance)
    return tools
