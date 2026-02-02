"""Factory for creating the shared CLI executor."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from src.cyberagent.tools.cli_executor.docker_env_executor import (
    EnvDockerCommandLineCodeExecutor,
)


def create_cli_executor() -> Optional[EnvDockerCommandLineCodeExecutor]:
    """
    Create a code executor for CLI tools.

    Returns:
        Code executor instance or None if AutoGen not available.
    """
    _maybe_set_docker_host_from_context()
    work_dir = Path("docker_cli_executor")
    work_dir.mkdir(exist_ok=True)

    try:
        image = os.getenv(
            "CLI_TOOLS_IMAGE",
            "ghcr.io/simonvanlaak/cyberneticagents-cli-tools:latest",
        )
        return EnvDockerCommandLineCodeExecutor(
            work_dir=work_dir,
            image=image,
            container_name="cybernetic-agents-cli-executor",
            auto_remove=True,
        )
    except Exception:
        return None


def _maybe_set_docker_host_from_context(
    config_path: Path | None = None,
    contexts_root: Path | None = None,
) -> str | None:
    if os.environ.get("DOCKER_HOST"):
        return None
    docker_dir = Path.home() / ".docker"
    config = config_path or (docker_dir / "config.json")
    if not config.exists():
        return None
    try:
        payload = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    context_name = payload.get("currentContext")
    if not isinstance(context_name, str) or not context_name:
        return None
    if context_name == "default":
        return None
    contexts_dir = contexts_root or (docker_dir / "contexts" / "meta")
    if not contexts_dir.exists():
        return None
    for meta_path in contexts_dir.glob("*/meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("Name") != context_name:
            continue
        host = meta.get("Endpoints", {}).get("docker", {}).get("Host")
        if isinstance(host, str) and host:
            if _unix_socket_accessible(host):
                os.environ["DOCKER_HOST"] = host
                return host
            return None
    return None


def _unix_socket_accessible(host: str) -> bool:
    prefix = "unix://"
    if not host.startswith(prefix):
        return True
    socket_path = Path(host[len(prefix) :])
    if not socket_path.exists():
        return False
    return os.access(socket_path, os.R_OK | os.W_OK)
