from __future__ import annotations

import asyncio
from datetime import datetime
import os
from pathlib import Path
import subprocess
from urllib.parse import urlparse, urlunparse

from src.cyberagent.cli.suggestion_queue import enqueue_suggestion
from src.cyberagent.cli.onboarding_constants import (
    DEFAULT_GIT_TOKEN_ENV,
    DEFAULT_TOKEN_USERNAME,
    ONBOARDING_SUMMARY_DIR,
)
from src.cyberagent.cli.onboarding_secrets import (
    VAULT_NAME,
    load_secret_from_1password,
)
from src.cyberagent.tools.cli_executor.cli_tool import CliTool
from src.cyberagent.tools.cli_executor.factory import create_cli_executor


def run_discovery_onboarding(args: object) -> Path | None:
    user_name = str(getattr(args, "user_name", "")).strip()
    repo_url = str(getattr(args, "repo_url", "")).strip()
    profile_links = list(getattr(args, "profile_links", []) or [])
    token_env = str(getattr(args, "token_env", DEFAULT_GIT_TOKEN_ENV)).strip()
    token_username = str(
        getattr(args, "token_username", DEFAULT_TOKEN_USERNAME)
    ).strip()

    repo_sync_allowed = True
    if not _ensure_onboarding_token(token_env):
        print("We need a GitHub read-only token to sync your private vault.")
        print(
            "Store it in the 1Password vault 'CyberneticAgents' as an item named "
            f"'{token_env}' with a field called 'credential'."
        )
        if not _prompt_continue_without_pkm("We couldn't access your PKM vault yet."):
            return None
        repo_sync_allowed = False

    cli_tool = _create_cli_tool()
    if cli_tool is None:
        print("CLI tool executor unavailable; cannot sync onboarding repo.")
        return None

    markdown_summary = (
        "PKM sync skipped. The onboarding interview will take longer without it."
    )
    if repo_sync_allowed:
        branch = _resolve_default_branch(repo_url, token_env, token_username)
        repo_path, success = _sync_obsidian_repo(
            cli_tool=cli_tool,
            repo_url=repo_url,
            branch=branch,
            token_env=token_env,
            token_username=token_username,
        )
        if success:
            markdown_summary = _summarize_markdown_repo(repo_path)
        elif not _prompt_continue_without_pkm("We couldn't sync your PKM vault."):
            return None
    profile_summary = _fetch_profile_links(cli_tool, profile_links)
    summary_text = _render_onboarding_summary(
        user_name=user_name,
        repo_url=repo_url,
        profile_links=profile_links,
        markdown_summary=markdown_summary,
        profile_summary=profile_summary,
    )
    summary_path = _write_onboarding_summary(summary_text)
    if summary_path is not None:
        enqueue_suggestion(
            build_onboarding_prompt(
                summary_path=summary_path, summary_text=summary_text
            )
        )
    return summary_path


def _ensure_onboarding_token(token_env: str) -> bool:
    if os.environ.get(token_env):
        return True
    loaded = load_secret_from_1password(
        vault_name=VAULT_NAME,
        item_name=token_env,
        field_label="credential",
    )
    if loaded:
        os.environ[token_env] = loaded
        return True
    return False


def _create_cli_tool() -> CliTool | None:
    executor = create_cli_executor()
    if executor is None:
        return None
    return CliTool(executor)


def _resolve_default_branch(repo_url: str, token_env: str, token_username: str) -> str:
    token = os.environ.get(token_env, "")
    authed_url = _build_authed_url(repo_url, token, token_username)
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--symref", authed_url, "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "main"
    if result.returncode != 0:
        return "main"
    for line in result.stdout.splitlines():
        if line.startswith("ref:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].startswith("refs/heads/"):
                return parts[1].split("refs/heads/")[-1]
    return "main"


def _build_authed_url(repo_url: str, token: str, username: str) -> str:
    if not token:
        return repo_url
    parsed = urlparse(repo_url)
    if parsed.scheme not in ("http", "https"):
        return repo_url
    userinfo = token if ":" in token else f"{username}:{token}"
    netloc = f"{userinfo}@{parsed.netloc}"
    return urlunparse(parsed._replace(netloc=netloc))


def _repo_name_from_url(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    path = parsed.path or repo_url
    name = path.rstrip("/").split("/")[-1]
    return name[:-4] if name.endswith(".git") else name


def _sync_obsidian_repo(
    *,
    cli_tool: CliTool,
    repo_url: str,
    branch: str,
    token_env: str,
    token_username: str,
) -> tuple[Path, bool]:
    repo_name = _repo_name_from_url(repo_url)
    dest = Path("data") / "obsidian" / repo_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = _run_cli_tool(
        cli_tool,
        "git-readonly-sync",
        repo=repo_url,
        dest=str(dest),
        branch=branch,
        depth=1,
        token_env=token_env,
        token_username=token_username,
    )
    if not result.get("success"):
        error = result.get("error") or result.get("raw_output", "")
        print(f"Failed to sync onboarding repo: {error}")
        return dest, False
    return dest, True


def _summarize_markdown_repo(repo_path: Path) -> str:
    files = sorted(repo_path.rglob("*.md"))
    limited = files[:1000]
    lines = [f"Markdown files analyzed: {len(limited)}"]
    for path in limited:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        excerpt = content.strip().splitlines()[:20]
        lines.append(f"\n## {path.relative_to(repo_path)}")
        if excerpt:
            lines.append("\n".join(excerpt))
    if len(files) > 1000:
        lines.append(f"\nSkipped {len(files) - 1000} markdown files (limit 1000).")
    return "\n".join(lines)


def _fetch_profile_links(cli_tool: CliTool, links: list[str]) -> str:
    if not links:
        return "No profile links provided."
    sections = []
    for link in links:
        result = _run_cli_tool(cli_tool, "web-fetch", url=link)
        if not result.get("success"):
            sections.append(f"## {link}\nFailed to fetch.")
            continue
        output = result.get("output")
        content = output.get("content") if isinstance(output, dict) else None
        if not content:
            sections.append(f"## {link}\nNo content.")
            continue
        sections.append(f"## {link}\n{content[:2000]}")
    return "\n".join(sections)


def _render_onboarding_summary(
    *,
    user_name: str,
    repo_url: str,
    profile_links: list[str],
    markdown_summary: str,
    profile_summary: str,
) -> str:
    links_text = "\n".join(profile_links) if profile_links else "None"
    return "\n".join(
        [
            "# Onboarding Summary",
            f"User: {user_name}",
            f"Repo: {repo_url}",
            "Profile links:",
            links_text,
            "",
            "# Repo Notes",
            markdown_summary,
            "",
            "# Profile Notes",
            profile_summary,
        ]
    )


def _prompt_continue_without_pkm(reason: str) -> bool:
    print(reason)
    print("The onboarding interview will take longer without your PKM.")
    response = input("Continue without PKM sync? [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def build_onboarding_prompt(summary_path: Path, summary_text: str) -> str:
    return "\n".join(
        [
            "## ONBOARDING DISCOVERY",
            "Use the onboarding summary to run a full discovery interview.",
            f"Summary file: {summary_path}",
            "",
            "# Onboarding Summary",
            summary_text,
        ]
    )


def _write_onboarding_summary(summary_text: str) -> Path | None:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    target_dir = ONBOARDING_SUMMARY_DIR / timestamp
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    path = target_dir / "summary.md"
    try:
        path.write_text(summary_text, encoding="utf-8")
    except OSError:
        return None
    return path


def _run_cli_tool(cli_tool: CliTool, tool_name: str, **kwargs) -> dict[str, object]:
    async def _execute() -> dict[str, object]:
        return await cli_tool.execute(tool_name, **kwargs)

    return asyncio.run(_execute())
