from __future__ import annotations

import os
from pathlib import Path
import subprocess
from urllib.parse import urlparse, urlunparse


def is_interpreter_shutdown_error(error: str) -> bool:
    return "cannot schedule new futures after interpreter shutdown" in error.lower()


def sync_obsidian_repo_with_git(
    *,
    repo_url: str,
    branch: str,
    dest: Path,
    token_env: str,
    token_username: str,
) -> tuple[bool, str | None]:
    token = os.environ.get(token_env, "")
    authed_url = _build_authed_url(repo_url, token, token_username)
    git_dir = dest / ".git"
    if dest.exists() and not git_dir.exists():
        return False, f"Destination exists and is not a git repository: {dest}"
    try:
        if git_dir.exists():
            subprocess.run(
                ["git", "-C", str(dest), "remote", "set-url", "origin", authed_url],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(dest), "fetch", "--depth", "1", "origin", branch],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(dest), "checkout", "-B", branch, f"origin/{branch}"],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    branch,
                    authed_url,
                    str(dest),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
    except subprocess.CalledProcessError as exc:
        error = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        return False, error
    except OSError as exc:
        return False, str(exc)
    return True, None


def _build_authed_url(repo_url: str, token: str, username: str) -> str:
    if not token:
        return repo_url
    parsed = urlparse(repo_url)
    if parsed.scheme not in ("http", "https"):
        return repo_url
    userinfo = token if ":" in token else f"{username}:{token}"
    netloc = f"{userinfo}@{parsed.netloc}"
    return urlunparse(parsed._replace(netloc=netloc))
