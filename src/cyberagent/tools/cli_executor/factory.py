"""
Factory for creating the OpenClaw CLI executor.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.cyberagent.tools.cli_executor.docker_env_executor import (
    EnvDockerCommandLineCodeExecutor,
)


def create_cli_executor() -> Optional[EnvDockerCommandLineCodeExecutor]:
    """
    Create a code executor for OpenClaw tools.

    Returns:
        Code executor instance or None if AutoGen not available.
    """
    work_dir = Path("docker_cli_executor")
    work_dir.mkdir(exist_ok=True)

    try:
        image = os.getenv(
            "OPENCLAW_TOOLS_IMAGE",
            "ghcr.io/simonvanlaak/cyberneticagents-openclaw-tools:latest",
        )
        return EnvDockerCommandLineCodeExecutor(
            work_dir=work_dir,
            image=image,
            container_name="cybernetic-agents-cli-executor",
            auto_remove=True,
        )
    except Exception:
        return None
