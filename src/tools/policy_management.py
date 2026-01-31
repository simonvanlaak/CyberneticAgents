# -*- coding: utf-8 -*-
"""
Policy Management Tool for System 5

Allows System 5 to CRUD manage policy prompts for Systems 1-4.
"""

from typing import List, Optional

from autogen_core import AgentId, CancellationToken
from autogen_core.models import FunctionExecutionResult
from autogen_core.tools import TextResultContent, ToolResult
from pydantic import BaseModel

from src.policy_database import (
    PolicyPrompt,
    create_policy_prompt,
    delete_policy_prompt,
    get_policy_prompt,
    list_policy_prompts,
    update_policy_prompt,
)
from src.tools.rbac_base_tool import RBACBaseTool


class PolicyManagementArgsType(BaseModel):
    system_id: str
    content: Optional[str] = None
    action: str  # create, read, update, delete, list


class PolicyManagement(RBACBaseTool):
    def __init__(self, agent_id: AgentId):
        description = (
            "Manage policy prompts for Systems 1-4. "
            "Policy prompts dictate how systems should operate and their goals/limitations. "
            "Actions: create, read, update, delete, list."
        )
        super().__init__(
            agent_id=agent_id,
            args_type=PolicyManagementArgsType,
            tool_name=self.__class__.__name__,
            description=description,
        )

    def _is_valid_system_id(self, system_id: str) -> bool:
        """Validate that system_id belongs to Systems 1-4."""
        valid_prefixes = [
            "root_1operations",
            "root_2coordination",
            "root_3control",
            "root_4intelligence",
        ]
        return any(system_id.startswith(prefix) for prefix in valid_prefixes)

    async def run(
        self, args: PolicyManagementArgsType, cancellation_token: CancellationToken
    ) -> FunctionExecutionResult:
        """Manage policy prompts for Systems 1-4."""
        print(f"[{self.agent_id.key}/{self.tool_name}] {args}")
        call_id = self.get_call_id()
        # Check RBAC permissions for the specific system
        if not self.is_action_allowed(args.system_id):
            return FunctionExecutionResult(
                content=f"Not authorized to manage policies for {args.system_id}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

        try:
            if args.action == "create":
                return await create_policy(args.system_id, args.content)
            elif args.action == "read":
                return await self._read_policy(args.system_id)
            elif args.action == "update":
                return await self._update_policy(args.system_id, args.content)
            elif args.action == "delete":
                return await self._delete_policy(args.system_id)
            elif args.action == "list":
                return await self._list_policies()
            else:
                return FunctionExecutionResult(
                    content=f"Invalid action: {args.action}",
                    name=self.tool_name,
                    call_id=call_id,
                    is_error=True,
                )
        except Exception as e:
            return FunctionExecutionResult(
                content=f"Failed to manage policy: {str(e)}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

    async def _read_policy(self, system_id: str) -> FunctionExecutionResult:
        """Read a policy prompt."""
        call_id = self.get_call_id()
        policy = get_policy_prompt(system_id)
        if not policy:
            return FunctionExecutionResult(
                content=f"No policy found for {system_id}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

        return FunctionExecutionResult(
            content=f"Policy retrieved for {system_id}:\n\n{str(policy.content)}",
            name=self.tool_name,
            call_id=call_id,
            is_error=False,
        )

    async def _update_policy(
        self, system_id: str, content: Optional[str]
    ) -> FunctionExecutionResult:
        """Update a policy prompt."""
        call_id = self.get_call_id()
        if not content:
            return FunctionExecutionResult(
                content="Content is required for update action",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

        policy = update_policy_prompt(system_id, content)
        if not policy:
            return FunctionExecutionResult(
                content=f"No policy found for {system_id}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

        return FunctionExecutionResult(
            content=f"Policy updated for {system_id}. Content length: {len(content)} chars",
            name=self.tool_name,
            call_id=call_id,
            is_error=False,
        )

    async def _delete_policy(self, system_id: str) -> FunctionExecutionResult:
        """Delete a policy prompt."""
        call_id = self.get_call_id()
        success = delete_policy_prompt(system_id)
        if not success:
            return FunctionExecutionResult(
                content=f"No policy found for {system_id}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

        return FunctionExecutionResult(
            content=f"Policy deleted for {system_id}",
            name=self.tool_name,
            call_id=call_id,
            is_error=False,
        )

    async def _list_policies(self) -> FunctionExecutionResult:
        """List all policy prompts."""
        call_id = self.get_call_id()
        policies: List[PolicyPrompt] = list_policy_prompts()
        if not policies:
            return FunctionExecutionResult(
                content="No policies found",
                name=self.tool_name,
                call_id=call_id,
                is_error=False,
            )

        # Format as simple list
        policy_list = [f"{p.system_id}: {len(str(p.content))} chars" for p in policies]
        return FunctionExecutionResult(
            content=f"Found {len(policies)} policies:\n\n" + "\n".join(policy_list),
            name=self.tool_name,
            call_id=call_id,
            is_error=False,
        )


async def create_policy(
    system_id: str, content: Optional[str]
) -> FunctionExecutionResult:
    """Create a new policy prompt."""
    if not content:
        return FunctionExecutionResult(
            content="Content is required for create action",
            name="PolicyManagement",
            call_id="create_policy",
            is_error=True,
        )

    try:
        create_policy_prompt(system_id, content)
        return FunctionExecutionResult(
            content=f"Policy created for {system_id}. Content length: {len(content)} chars",
            name="PolicyManagement",
            call_id="create_policy",
            is_error=False,
        )
    except ValueError as e:
        return FunctionExecutionResult(
            content=str(e),
            name="PolicyManagement",
            call_id="create_policy",
            is_error=True,
        )
