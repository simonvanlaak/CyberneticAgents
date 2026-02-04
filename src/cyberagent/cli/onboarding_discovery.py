from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime
import os
from pathlib import Path
import subprocess
import threading
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse

from src.cyberagent.cli.suggestion_queue import enqueue_suggestion
from src.cyberagent.cli.onboarding_constants import (
    DEFAULT_GIT_TOKEN_ENV,
    DEFAULT_TOKEN_USERNAME,
    GIT_SYNC_TIMEOUT_SECONDS,
    ONBOARDING_SUMMARY_DIR,
)
from src.cyberagent.cli.onboarding_secrets import (
    VAULT_NAME,
    check_onepassword_cli_access,
    has_onepassword_auth,
    load_secret_from_1password_with_error,
)
from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.onboarding_memory import (
    store_onboarding_memory,
    store_onboarding_memory_entry,
)
from src.cyberagent.memory.models import MemoryLayer, MemoryPriority, MemorySource

from src.cyberagent.tools.cli_executor.cli_tool import CliTool
from src.cyberagent.tools.cli_executor.factory import create_cli_executor

logger = logging.getLogger(__name__)


def run_discovery_onboarding(args: object) -> Path | None:
    return _run_discovery_pipeline(
        args,
        team_id=None,
        allow_prompt=True,
        enqueue_prompt=True,
    )


def start_discovery_background(args: object, team_id: int) -> None:
    thread = threading.Thread(
        target=_run_discovery_pipeline,
        kwargs={
            "args": args,
            "team_id": team_id,
            "allow_prompt": False,
            "enqueue_prompt": False,
        },
        daemon=True,
    )
    thread.start()


def _run_discovery_pipeline(
    args: object,
    *,
    team_id: int | None,
    allow_prompt: bool,
    enqueue_prompt: bool,
) -> Path | None:
    user_name = str(getattr(args, "user_name", "")).strip()
    repo_url = str(getattr(args, "repo_url", "")).strip()
    profile_links = list(getattr(args, "profile_links", []) or [])
    token_env = str(getattr(args, "token_env", DEFAULT_GIT_TOKEN_ENV)).strip()
    token_username = str(
        getattr(args, "token_username", DEFAULT_TOKEN_USERNAME)
    ).strip()

    repo_sync_allowed = True
    if not _ensure_onboarding_token(token_env):
        print(get_message("onboarding_discovery", "need_github_token"))
        print(
            get_message(
                "onboarding_discovery",
                "store_github_token",
                vault_name=VAULT_NAME,
                token_env=token_env,
            )
        )
        if allow_prompt:
            if not _prompt_continue_without_pkm(
                get_message("onboarding_discovery", "pkm_access_unavailable")
            ):
                return None
        repo_sync_allowed = False

    cli_tool = _create_cli_tool()
    if cli_tool is None:
        print(get_message("onboarding_discovery", "cli_tool_unavailable"))
        return None

    profile_summary = _fetch_profile_links(
        cli_tool,
        profile_links,
        on_entry=(
            _build_profile_link_entry_writer(team_id) if team_id is not None else None
        ),
    )
    if team_id is not None and profile_summary.strip():
        store_onboarding_memory_entry(
            team_id=team_id,
            content=profile_summary,
            tags=["onboarding", "profile_links_summary"],
            source=MemorySource.TOOL,
            priority=MemoryPriority.MEDIUM,
            layer=MemoryLayer.SESSION,
        )

    markdown_summary = get_message("onboarding_discovery", "pkm_sync_skipped")
    if repo_sync_allowed:
        print(get_message("onboarding_discovery", "pkm_sync_starting"))
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
            if team_id is not None and markdown_summary.strip():
                store_onboarding_memory_entry(
                    team_id=team_id,
                    content=markdown_summary,
                    tags=["onboarding", "pkm"],
                    source=MemorySource.IMPORT,
                    priority=MemoryPriority.HIGH,
                    layer=MemoryLayer.LONG_TERM,
                )
        elif allow_prompt:
            if not _prompt_continue_without_pkm(
                get_message("onboarding_discovery", "pkm_sync_failed")
            ):
                return None
    summary_text = _render_onboarding_summary(
        user_name=user_name,
        repo_url=repo_url,
        profile_links=profile_links,
        markdown_summary=markdown_summary,
        profile_summary=profile_summary,
    )
    summary_path = _write_onboarding_summary(summary_text)
    if team_id is not None:
        store_onboarding_memory(team_id, summary_path)
    if summary_path is not None and enqueue_prompt:
        enqueue_suggestion(
            build_onboarding_prompt(
                summary_path=summary_path, summary_text=summary_text
            )
        )
    return summary_path


def _ensure_onboarding_token(token_env: str) -> bool:
    if os.environ.get(token_env):
        return True
    loaded, error = load_secret_from_1password_with_error(
        vault_name=VAULT_NAME,
        item_name=token_env,
        field_label="credential",
    )
    if loaded:
        os.environ[token_env] = loaded
        return True
    if has_onepassword_auth():
        if error and _is_onepassword_auth_error(error):
            print(
                get_message(
                    "onboarding_discovery",
                    "onepassword_cli_not_ready",
                    reason=error,
                )
            )
        else:
            ok, detail = check_onepassword_cli_access()
            if not ok and detail:
                print(
                    get_message(
                        "onboarding_discovery",
                        "onepassword_cli_not_ready",
                        reason=detail,
                    )
                )
    return False


def _is_onepassword_auth_error(error: str) -> bool:
    lowered = error.lower()
    return any(
        fragment in lowered
        for fragment in (
            "not signed in",
            "sign in",
            "not authenticated",
            "unauthorized",
            "permission denied",
            "forbidden",
        )
    )


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
    stop_event = _start_sync_notifier()
    result = _run_cli_tool(
        cli_tool,
        "git-readonly-sync",
        repo=repo_url,
        dest=str(dest),
        branch=branch,
        depth=1,
        timeout_seconds=GIT_SYNC_TIMEOUT_SECONDS,
        **{
            "token-env": token_env,
            "token-username": token_username,
        },
    )
    stop_event.set()
    if not result.get("success"):
        error = result.get("error") or result.get("stderr") or result.get("raw_output")
        if not error:
            error = f"Unknown error (result={result})" if result else "Unknown error"
        print(get_message("onboarding_discovery", "failed_sync_repo", error=error))
        return dest, False
    return dest, True


def _start_sync_notifier() -> threading.Event:
    stop_event = threading.Event()

    def _notify() -> None:
        while not stop_event.wait(60):
            print(get_message("onboarding_discovery", "pkm_sync_still_running"))

    threading.Thread(target=_notify, daemon=True).start()
    return stop_event


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


def _fetch_profile_links(
    cli_tool: CliTool,
    links: list[str],
    on_entry: Callable[[str, str], None] | None = None,
) -> str:
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
        excerpt = content[:2000]
        sections.append(f"## {link}\n{excerpt}")
        if on_entry is not None:
            on_entry(link, excerpt)
    return "\n".join(sections)


def _build_profile_link_entry_writer(
    team_id: int,
) -> Callable[[str, str], None]:
    def _writer(link: str, content: str) -> None:
        payload = f"Profile link: {link}\n\n{content}".strip()
        store_onboarding_memory_entry(
            team_id=team_id,
            content=payload,
            tags=["onboarding", "profile_link"],
            source=MemorySource.TOOL,
            priority=MemoryPriority.MEDIUM,
            layer=MemoryLayer.SESSION,
        )

    return _writer


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
    print(get_message("onboarding_discovery", "onboarding_interview_longer"))
    try:
        response = (
            input(get_message("onboarding_discovery", "continue_without_pkm_prompt"))
            .strip()
            .lower()
        )
    except EOFError:
        return False
    return response in {"y", "yes"}


def build_onboarding_prompt(summary_path: Path, summary_text: str) -> str:
    return "\n".join(
        [
            "## ONBOARDING DISCOVERY",
            "Use the onboarding summary to run a full discovery interview.",
            "Before each question, check memory for new onboarding entries.",
            "Log user responses into memory as you learn them.",
            "If the user mentions a specific company, city, product, or industry",
            "that is not in memory, trigger background web research and store",
            "the results in memory for future questions.",
            f"Summary file: {summary_path}",
            "",
            "# Onboarding Summary",
            summary_text,
        ]
    )


def build_onboarding_interview_prompt(
    *,
    user_name: str,
    repo_url: str,
    profile_links: list[str],
    first_question: str,
) -> str:
    links_text = "\n".join(profile_links) if profile_links else "None"
    return "\n".join(
        [
            "## ONBOARDING INTERVIEW",
            "Start the onboarding interview now.",
            f"The first question has already been sent: {first_question}",
            "Wait for the user response before sending the next question.",
            "Before each question, check memory for new onboarding entries.",
            "Log user responses into memory as you learn them.",
            "If the user mentions a specific company, city, product, or industry",
            "that is not in memory, trigger background web research and store",
            "the results in memory for future questions.",
            "",
            f"User: {user_name}",
            f"Repo: {repo_url}",
            "Profile links:",
            links_text,
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


def _run_cli_tool(
    cli_tool: Any,
    tool_name: str,
    timeout_seconds: int | None = None,
    **kwargs: object,
) -> dict[str, object]:
    async def _execute() -> dict[str, object]:
        executor = getattr(cli_tool, "executor", None)
        started = False
        if executor is not None:
            start = getattr(executor, "start", None)
            if callable(start) and not getattr(executor, "_running", False):
                try:
                    result = start()
                    if inspect.isawaitable(result):
                        await result
                    started = True
                except Exception as exc:
                    return {"success": False, "error": str(exc)}
        try:
            try:
                execute_task = cli_tool.execute(
                    tool_name, timeout_seconds=timeout_seconds, **kwargs
                )
                if timeout_seconds is not None:
                    return await asyncio.wait_for(execute_task, timeout=timeout_seconds)
                return await execute_task
            except asyncio.TimeoutError:
                return {"success": False, "error": "Timeout"}
        finally:
            if started and executor is not None:
                stop = getattr(executor, "stop", None)
                if callable(stop):
                    try:
                        result = stop()
                        if inspect.isawaitable(result):
                            await result
                    except RuntimeError as exc:
                        logger.warning(
                            "Failed to stop CLI tool executor after %s: %s",
                            tool_name,
                            exc,
                        )

    return asyncio.run(_execute())
