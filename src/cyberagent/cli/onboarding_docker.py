from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from src.cyberagent.tools.cli_executor.skill_loader import load_skill_definitions
from src.cyberagent.tools.cli_executor.skill_runtime import DEFAULT_SKILLS_ROOT


def skills_require_docker() -> bool:
    skills = load_skill_definitions(DEFAULT_SKILLS_ROOT)
    return len(skills) > 0


def check_docker_socket_access() -> bool:
    if not skills_require_docker():
        return True
    if not shutil.which("docker"):
        return False
    socket_path = _get_docker_socket_path()
    if socket_path is None:
        return True
    if not socket_path.exists():
        return True
    if os.access(socket_path, os.R_OK | os.W_OK):
        return True
    print(f"Docker socket is not accessible: {socket_path}")
    print("Fix Docker socket permissions and re-run onboarding.")
    return False


def check_docker_available() -> bool:
    docker_path = shutil.which("docker")
    if not docker_path:
        if not skills_require_docker():
            print(
                "Docker not found, but no Docker-based skills are configured. "
                "Continuing without tool execution."
            )
            return True
        print("Docker is required for tool execution but was not found in PATH.")
        return False
    try:
        result = subprocess.run(
            [docker_path, "info"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        print("Docker is installed but not reachable. Is the daemon running?")
        return False
    if result.returncode != 0:
        stderr = (result.stderr or "").lower()
        if "permission denied" in stderr:
            print("Docker is running but the current user cannot access the daemon.")
            print(
                "Fix: add your user to the docker group or run the CLI as the user "
                "that owns the Docker Desktop socket."
            )
            return False
        if not skills_require_docker():
            print(
                "Docker is installed but not reachable. "
                "Continuing without tool execution because no Docker-based "
                "skills are configured."
            )
            return True
        print("Docker is installed but not reachable. Is the daemon running?")
        return False
    return True


def check_cli_tools_image_available() -> bool:
    if not skills_require_docker():
        return True
    docker_path = shutil.which("docker")
    if not docker_path:
        return False
    image = os.getenv(
        "CLI_TOOLS_IMAGE",
        "ghcr.io/simonvanlaak/cyberneticagents-cli-tools:latest",
    )
    try:
        result = subprocess.run(
            [docker_path, "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        print("Unable to verify the CLI tools image. Is Docker running?")
        return False
    if result.returncode == 0:
        return True
    stderr = (result.stderr or "").lower()
    if "permission denied" in stderr:
        print("Unable to access the Docker daemon (permission denied).")
        print(
            "Fix: add your user to the docker group or run the CLI as the user "
            "that owns the Docker Desktop socket."
        )
        return False
    print(
        "CLI tools image is not available. Build or pull the image, then re-run "
        "onboarding."
    )
    print(f"Expected image: {image}")
    return False


def _get_docker_socket_path() -> Path | None:
    docker_host = os.environ.get("DOCKER_HOST", "")
    if docker_host.startswith("unix://"):
        socket_path = docker_host[len("unix://") :]
        if socket_path:
            return Path(socket_path)
        return None
    if docker_host:
        return None
    return Path("/var/run/docker.sock")
