from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from src.cyberagent.tools.cli_executor.skill_loader import load_skill_definitions
from src.cyberagent.tools.cli_executor.skill_runtime import DEFAULT_SKILLS_ROOT
from src.cyberagent.cli.message_catalog import get_message


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
    print(
        get_message(
            "onboarding_docker",
            "socket_inaccessible",
            socket_path=socket_path,
        )
    )
    print(get_message("onboarding_docker", "fix_socket_permissions"))
    return False


def check_docker_available() -> bool:
    docker_path = shutil.which("docker")
    if not docker_path:
        if not skills_require_docker():
            print(get_message("onboarding_docker", "docker_not_found_no_skills"))
            return True
        print(get_message("onboarding_docker", "docker_required_missing"))
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
        print(get_message("onboarding_docker", "docker_unreachable"))
        return False
    if result.returncode != 0:
        stderr = (result.stderr or "").lower()
        if "permission denied" in stderr:
            print(get_message("onboarding_docker", "docker_permission_denied"))
            print(get_message("onboarding_docker", "docker_permission_fix"))
            return False
        if not skills_require_docker():
            print(get_message("onboarding_docker", "docker_unreachable_no_skills"))
            return True
        print(get_message("onboarding_docker", "docker_unreachable"))
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
        print(get_message("onboarding_docker", "cli_tools_image_unverified"))
        return False
    if result.returncode == 0:
        return True
    stderr = (result.stderr or "").lower()
    if "permission denied" in stderr:
        print(get_message("onboarding_docker", "docker_daemon_permission_denied"))
        print(get_message("onboarding_docker", "docker_permission_fix"))
        return False
    print(get_message("onboarding_docker", "cli_tools_image_missing"))
    print(get_message("onboarding_docker", "expected_image", image=image))
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
