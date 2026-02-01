"""
OpenClaw Tool Wrapper for AutoGen Agents

Provides access to OpenClaw CLI tools and skills from within AutoGen agents.
"""

import json
import logging
from typing import Any, Dict, Optional

from autogen_core import CancellationToken
from autogen_core.code_executor import CodeBlock

from src.tools.cli_executor import secrets

logger = logging.getLogger(__name__)


class OpenClawTool:
    """
    Wrapper for executing OpenClaw CLI tools via AutoGen's code executor.

    Example:
        tool = OpenClawTool(executor)
        result = await tool.execute("web_search", query="test", count=1)
    """

    def __init__(self, executor):
        """
        Initialize the OpenClaw tool wrapper.

        Args:
            executor: AutoGen code executor (Docker or Local)
        """
        self.executor = executor

    async def execute(
        self,
        tool_name: str,
        agent_id: Optional[str] = None,
        subcommand: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute an OpenClaw tool with given parameters.

        Args:
            tool_name: Name of the OpenClaw tool (e.g., "web_search", "exec")
            agent_id: ID of the agent making the request (for RBAC)
            **kwargs: Parameters for the tool

        Returns:
            Dictionary with {"success": bool, "output": ..., "error": ...}
        """
        # Check RBAC permission if agent_id provided
        if agent_id and not self._check_permission(agent_id, tool_name):
            return {
                "success": False,
                "error": f"Agent {agent_id} not authorized to use {tool_name}",
            }

        # Inject secrets into the executor environment
        if callable(getattr(type(self.executor), "set_exec_env", None)):
            try:
                tool_secrets = secrets.get_tool_secrets(tool_name)
                self.executor.set_exec_env(tool_secrets)
            except ValueError as exc:
                return {
                    "success": False,
                    "error": str(exc),
                }

        # Convert kwargs to CLI arguments
        args = self._build_cli_args(kwargs)
        subcommand_part = f"{subcommand} " if subcommand else ""

        # Create shell command
        command = f"openclaw {tool_name} {subcommand_part}{args}".strip()

        logger.info(f"Executing OpenClaw command: {command}")

        try:
            # Execute in Docker container
            result = await self.executor.execute_code_blocks(
                code_blocks=[CodeBlock(language="bash", code=command)],
                cancellation_token=CancellationToken(),
            )
            return self._parse_result(result)

        except Exception as e:
            logger.error(f"OpenClaw tool {tool_name} failed: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            if callable(getattr(type(self.executor), "set_exec_env", None)):
                self.executor.set_exec_env({})

    def _check_permission(self, agent_id: str, tool_name: str) -> bool:
        """Check if agent has permission to use the tool."""
        try:
            from src.rbac.enforcer import check_tool_permission

            return check_tool_permission(agent_id, tool_name)
        except ImportError:
            logger.warning("RBAC enforcer not available, allowing all tool access")
            return True

    def _build_cli_args(self, kwargs: Dict[str, Any]) -> str:
        """Convert kwargs to CLI argument string."""
        args = []

        for key, value in kwargs.items():
            # Handle boolean flags
            if isinstance(value, bool):
                if value:
                    args.append(f"--{key}")
                continue

            # Handle lists
            if isinstance(value, list):
                for item in value:
                    args.append(f"--{key} {item}")
                continue

            # Handle strings/numbers
            args.append(f"--{key} {value}")

        return " ".join(args)

    def _parse_result(self, result) -> Dict[str, Any]:
        """Parse the execution result."""
        if result.exit_code == 0:
            try:
                # Try to parse JSON output
                output = json.loads(result.output)
                return {"success": True, "output": output, "raw_output": result.output}
            except json.JSONDecodeError:
                # Fall back to raw output if not JSON
                return {
                    "success": True,
                    "output": result.output,
                    "raw_output": result.output,
                }
        else:
            return {
                "success": False,
                "error": result.output,
                "raw_output": result.output,
            }
