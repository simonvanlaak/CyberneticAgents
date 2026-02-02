"""
Docker code executor with explicit environment injection per exec.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

from autogen_core import CancellationToken
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor

logger = logging.getLogger(__name__)


class EnvDockerCommandLineCodeExecutor(DockerCommandLineCodeExecutor):
    """
    Docker executor that injects an explicit environment into each exec_run.

    This avoids writing secrets to disk and keeps them process-scoped.
    """

    def __init__(
        self,
        *args,
        exec_env: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._exec_env: Dict[str, str] = exec_env or {}
        self.last_stderr: str = ""

    def set_exec_env(self, exec_env: Optional[Dict[str, str]]) -> None:
        """
        Update the explicit environment passed to exec_run.

        Args:
            exec_env: Mapping of environment variables to inject.
        """
        self._exec_env = exec_env or {}

    def _build_exec_env(self) -> Dict[str, str]:
        return dict(self._exec_env)

    async def _execute_command(
        self, command: List[str], cancellation_token: CancellationToken
    ) -> Tuple[str, int]:
        if self._container is None or not self._running:
            raise ValueError(
                "Container is not running. Must first be started with either start or a context manager."
            )

        env = self._build_exec_env()
        exec_kwargs = {"environment": env} if env else {}
        exec_kwargs["demux"] = True
        exec_task = asyncio.create_task(
            asyncio.to_thread(self._container.exec_run, command, **exec_kwargs)
        )
        cancellation_token.link_future(exec_task)

        try:
            result = await exec_task
            exit_code = result.exit_code
            stdout, stderr = _decode_exec_output(result.output)
            self.last_stderr = stderr
            output = stdout
            if exit_code == 124:
                output += "\n Timeout"
            return output, exit_code
        except asyncio.CancelledError:
            if self._loop and not self._loop.is_closed():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self._kill_running_command(command), self._loop
                    )
                    self._cancellation_futures.append(future)
                except Exception as e:
                    logger.exception("Failed to schedule kill command on loop: %s", e)
            return "Code execution was cancelled.", 1


def _decode_exec_output(output: object) -> tuple[str, str]:
    if isinstance(output, tuple):
        stdout_bytes, stderr_bytes = output
        stdout = stdout_bytes.decode("utf-8") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8") if stderr_bytes else ""
        return stdout, stderr
    if isinstance(output, bytes):
        return output.decode("utf-8"), ""
    return str(output), ""
