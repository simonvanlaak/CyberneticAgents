#!/usr/bin/env python3
"""Read-only git sync helper used inside the CLI tools container."""

import argparse
import os
import subprocess
from urllib.parse import urlparse, urlunparse


def _build_authed_url(repo_url: str, token: str, username: str | None) -> str:
    parsed = urlparse(repo_url)
    if parsed.scheme not in ("http", "https"):
        return repo_url
    user = username or "x-access-token"
    userinfo = token if ":" in token else f"{user}:{token}"
    netloc = f"{userinfo}@{parsed.netloc}"
    return urlunparse(parsed._replace(netloc=netloc))


def _run_git(args: list[str], cwd: str | None = None) -> None:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only git sync helper.")
    parser.add_argument("--repo", required=True, help="Repository URL (https or ssh).")
    parser.add_argument("--dest", required=True, help="Destination directory.")
    parser.add_argument("--branch", default="main", help="Branch to sync.")
    parser.add_argument("--depth", type=int, default=1, help="Shallow clone depth.")
    parser.add_argument(
        "--token-env",
        default=None,
        help="Env var name holding a read-only access token.",
    )
    parser.add_argument(
        "--token-username",
        default=None,
        help="Username to pair with the token (defaults to x-access-token).",
    )
    args = parser.parse_args()

    repo_url = args.repo
    if args.token_env:
        token = os.environ.get(args.token_env, "")
        if not token:
            raise SystemExit(f"Missing required token in env var {args.token_env}.")
        repo_url = _build_authed_url(repo_url, token, args.token_username)

    if os.path.isdir(os.path.join(args.dest, ".git")):
        _run_git(["fetch", "--prune", "origin"], cwd=args.dest)
    else:
        _run_git(["clone", "--depth", str(args.depth), repo_url, args.dest])

    _run_git(["checkout", args.branch], cwd=args.dest)
    _run_git(["reset", "--hard", f"origin/{args.branch}"], cwd=args.dest)


if __name__ == "__main__":
    main()
