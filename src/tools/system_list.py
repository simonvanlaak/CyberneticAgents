# -*- coding: utf-8 -*-
"""
System List Tool

Lists all available system IDs in the VSM system.
"""

from autogen_core import AgentId, CancellationToken
from autogen_core.models import FunctionExecutionResult
from pydantic import BaseModel

from src.tools.rbac_base_tool import RBACBaseTool


class SystemListArgsType(BaseModel):
    pass


class SystemList(RBACBaseTool):
    def __init__(self, agent_id: AgentId):
        name = __class__.__name__
        # SystemList has no RBAC restrictions - all systems can list
        description = (
            "List all available system IDs in the VSM system. No Parameters Required."
        )

        super().__init__(
            agent_id=agent_id,
            args_type=SystemListArgsType,
            tool_name=name,
            description=description,
        )

    async def run(
        self, args, cancellation_token: CancellationToken
    ) -> FunctionExecutionResult:
        """List all system IDs."""
        print(f"[{self.agent_id.key}/{self.tool_name}] {args}")
        call_id = self.get_call_id()
        try:
            system_ids = self.get_allowed_actions()
            return FunctionExecutionResult(
                content=f"Found {len(system_ids)} systems: {', '.join(system_ids)}",
                name=self.tool_name,
                call_id=call_id,
                is_error=False,
            )
        except Exception as e:
            print(f"[{self.__class__.__name__}]: Failed to list systems: {str(e)}")
            return FunctionExecutionResult(
                content=f"Failed to list systems: {str(e)}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )
