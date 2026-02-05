"""CLI tool wrapper for AutoGen agents."""

import inspect
import json
import logging
import shlex
from typing import Any, Callable, Dict, Optional

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
                token_env = kwargs.get("token_env") or kwargs.get("token-env")
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

        if subcommand:
            logger.info("Executing CLI tool: %s %s", tool_name, subcommand)
        else:
            logger.info("Executing CLI tool: %s", tool_name)

        original_timeout = _get_executor_timeout(self.executor)
        if timeout_seconds is not None:
            _set_executor_timeout(self.executor, timeout_seconds)

        try:
            await _ensure_executor_started(self.executor)
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
        check_tool_permission = _get_check_tool_permission()
        if check_tool_permission is None:
            logger.warning("RBAC enforcer not available; denying tool access.")
            return False
        return check_tool_permission(agent_id, tool_name)

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
                    args.append(f"--{key} {shlex.quote(str(item))}")
                continue

            # Handle strings/numbers
            args.append(f"--{key} {shlex.quote(str(value))}")

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
    timeout = getattr(executor, "_timeout", None)
    return timeout if isinstance(timeout, int) else None


def _get_check_tool_permission() -> Optional[Callable[[str, str], bool]]:
    try:
        from src.rbac.enforcer import check_tool_permission
    except ImportError:
        return None
    return check_tool_permission


async def _ensure_executor_started(executor: Any) -> None:
    start = getattr(executor, "start", None)
    if not callable(start):
        return
    if getattr(executor, "_running", False):
        return
    result = start()
    if inspect.isawaitable(result):
        await result


def _set_executor_timeout(executor: Any, timeout_seconds: int) -> None:
    if timeout_seconds < 1:
        raise ValueError("Timeout must be greater than or equal to 1.")
    if hasattr(executor, "_timeout"):
        setattr(executor, "_timeout", timeout_seconds)


def _get_executor_stderr(executor: Any) -> str:
    return str(getattr(executor, "last_stderr", "") or "")
