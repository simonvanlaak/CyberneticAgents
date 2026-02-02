"""CLI tool wrapper for AutoGen agents."""

import json
import logging
from typing import Any, Dict, Optional

from autogen_core import CancellationToken
from autogen_core.code_executor import CodeBlock

from src.cyberagent.db.models.system import get_system_from_agent_id
from src.cyberagent.services import systems as systems_service
from src.cyberagent.tools.cli_executor import secrets

logger = logging.getLogger(__name__)


class CliTool:
    """Wrapper for executing command-line tools via the code executor."""

    def __init__(self, executor):
        """
        Initialize the CLI tool wrapper.

        Args:
            executor: AutoGen code executor (Docker or Local)
        """
        self.executor = executor

    async def execute(
        self,
        tool_name: str,
        agent_id: Optional[str] = None,
        subcommand: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        skill_name: Optional[str] = None,
        required_env: Optional[list[str] | tuple[str, ...]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute a CLI tool with given parameters.

        Args:
            tool_name: Name of the CLI tool (e.g., "web_search", "git")
            agent_id: ID of the agent making the request (for RBAC)
            skill_name: Skill name for skill-permission enforcement.
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
        if skill_name:
            if not agent_id:
                return {
                    "success": False,
                    "error": "Skill permission check requires agent_id.",
                }
            allowed, details = self._check_skill_permission(agent_id, skill_name)
            if not allowed:
                response = {
                    "success": False,
                    "error": "Skill permission denied.",
                    "details": details,
                }
                if details:
                    response.update(details)
                return response

        # Inject secrets into the executor environment
        if callable(getattr(type(self.executor), "set_exec_env", None)):
            try:
                extra_required_env = list(required_env or [])
                token_env = kwargs.get("token_env")
                if token_env:
                    extra_required_env.append(str(token_env))
                tool_secrets = secrets.get_tool_secrets(
                    tool_name, required_env=extra_required_env
                )
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
        command = f"{tool_name} {subcommand_part}{args}".strip()

        logger.info(f"Executing CLI command: {command}")

        original_timeout = _get_executor_timeout(self.executor)
        if timeout_seconds is not None:
            _set_executor_timeout(self.executor, timeout_seconds)

        try:
            # Execute in Docker container
            result = await self.executor.execute_code_blocks(
                code_blocks=[CodeBlock(language="bash", code=command)],
                cancellation_token=CancellationToken(),
            )
            parsed = self._parse_result(result)
            stderr = _get_executor_stderr(self.executor)
            if stderr:
                parsed["stderr"] = stderr
            return parsed

        except Exception as e:
            logger.error(f"CLI tool {tool_name} failed: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            if callable(getattr(type(self.executor), "set_exec_env", None)):
                self.executor.set_exec_env({})
            if original_timeout is not None:
                _set_executor_timeout(self.executor, original_timeout)

    def _check_permission(self, agent_id: str, tool_name: str) -> bool:
        """Check if agent has permission to use the tool."""
        try:
            from src.rbac.enforcer import check_tool_permission

            return check_tool_permission(agent_id, tool_name)
        except ImportError:
            logger.warning("RBAC enforcer not available, allowing all tool access")
            return True

    def _check_skill_permission(
        self, agent_id: str, skill_name: str
    ) -> tuple[bool, dict[str, Any] | None]:
        system = get_system_from_agent_id(agent_id)
        if system is None:
            raise ValueError(f"System not found for agent_id {agent_id}.")
        allowed, reason = systems_service.can_execute_skill(system.id, skill_name)
        if allowed:
            return True, None
        return False, {
            "team_id": system.team_id,
            "system_id": system.id,
            "skill_name": skill_name,
            "failed_rule_category": reason,
        }

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


def _get_executor_timeout(executor: Any) -> Optional[int]:
    return getattr(executor, "_timeout", None)


def _set_executor_timeout(executor: Any, timeout_seconds: int) -> None:
    if timeout_seconds < 1:
        raise ValueError("Timeout must be greater than or equal to 1.")
    if hasattr(executor, "_timeout"):
        setattr(executor, "_timeout", timeout_seconds)


def _get_executor_stderr(executor: Any) -> str:
    return str(getattr(executor, "last_stderr", "") or "")
