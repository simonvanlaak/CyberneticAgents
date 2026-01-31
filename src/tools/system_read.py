# -*- coding: utf-8 -*-
"""
System Read Tool

Reads detailed information about specific systems in the VSM system.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from autogen_core import AgentId, CancellationToken
from autogen_core.models import FunctionExecutionResult
from pydantic import BaseModel

from src.policy_database import get_policy_prompt
from src.tools.rbac_base_tool import RBACBaseTool


@dataclass
class SystemReadRequest:
    target_system_id: str
    sender: str


class SystemReadArgsType(BaseModel):
    target_system_id: str


class SystemRead(RBACBaseTool):
    def __init__(self, agent_id: AgentId):
        name = __class__.__name__
        # First call super().__init__ to set up the base class
        super().__init__(
            agent_id=agent_id,
            args_type=SystemReadArgsType,
            tool_name=name,
            description="Read detailed system information.",  # Temporary description
        )

        # Now we can call get_allowed_actions since agent_id is set
        allowed_targets = self.get_allowed_actions()

        if allowed_targets:
            # Update the description with allowed targets
            self._description = (
                f"Read detailed system information."
                f"Allowed target_system_id: {', '.join(allowed_targets)}"
            )
        else:
            raise ValueError("No system read permissions available.")

    async def run(
        self, args: SystemReadArgsType, cancellation_token: CancellationToken
    ) -> FunctionExecutionResult:
        """Read system information."""
        print(f"[{self.agent_id.key}/{self.tool_name}] {args}")
        call_id = self.get_call_id()
        # Validate RBAC permissions
        if not self.is_action_allowed(args.target_system_id):
            return FunctionExecutionResult(
                content="Not authorized to read this system",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

        # Collect system information
        system_info = await self._collect_system_info(args.target_system_id)

        # Convert system info to JSON string
        system_info_json = json.dumps(system_info, indent=2)

        return FunctionExecutionResult(
            content=f"System information for {args.target_system_id}:\n{system_info_json}",
            name=self.tool_name,
            call_id=call_id,
            is_error=False,
        )

    async def _collect_system_info(self, system_id: str) -> Dict[str, Any]:
        """Collect comprehensive system information."""
        return {
            "system_id": system_id,
            "tools": await self._get_system_tools(system_id),
            "policy_preview": await self._get_policy_preview(system_id),
        }

    async def _get_system_tools(self, system_id: str) -> List[Dict[str, str]]:
        """Get list of tools available to the system."""
        from autogen_core import AgentId

        from src.tools.tool_router import get_tools

        try:
            agent_id = AgentId("VSMSystemAgent", system_id)
            tools = get_tools(agent_id)
            return [
                {"name": tool.name, "description": tool.description} for tool in tools
            ]
        except Exception:
            return []

    async def _get_policy_preview(self, system_id: str) -> Optional[str]:
        """Get first 100 chars of policy if exists."""
        try:
            policy = get_policy_prompt(system_id)
            return policy.content[:100] + "..." if policy else None
        except Exception:
            return None
