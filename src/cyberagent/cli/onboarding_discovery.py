from __future__ import annotations

import asyncio
import json
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
    DEFAULT_NOTION_TOKEN_ENV,
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
    fetch_onboarding_memory_contents,
    store_onboarding_memory,
    store_onboarding_memory_entry,
)
from src.cyberagent.core.paths import get_repo_root, resolve_data_path
from src.cyberagent.db.models.system import get_system_by_type
from src.cyberagent.memory.models import MemoryLayer, MemoryPriority, MemorySource
from src.enums import SystemType

from src.cyberagent.tools.cli_executor.cli_tool import CliTool
from src.cyberagent.tools.cli_executor.factory import create_cli_executor

logger = logging.getLogger(__name__)
MARKDOWN_PKM_FILE_LIMIT = 1000
MARKDOWN_PKM_LINES_PER_FILE = 20
ONBOARDING_PROMPT_SUMMARY_CHAR_LIMIT = 12000


def run_discovery_onboarding(args: object, team_id: int | None = None) -> Path | None:
    return _run_discovery_pipeline(
        args,
        team_id=team_id,
        allow_prompt=True,
        enqueue_prompt=True,
    )


def start_discovery_background(
    args: object,
    team_id: int,
    on_complete: Callable[[Path], None] | None = None,
) -> None:
    if os.environ.get("CYBERAGENT_DISABLE_BACKGROUND_DISCOVERY"):
        logger.info("Background discovery disabled via env override.")
        return

    # Background discovery should not block the onboarding interview, but we still
    # want it to enqueue the onboarding discovery prompt once the sync completes
    # so the agent can incorporate PKM/profile context as soon as it's available.
    def _run_and_finalize() -> None:
        summary_path = _run_discovery_pipeline(
            args=args,
            team_id=team_id,
            allow_prompt=False,
            enqueue_prompt=True,
        )
        if summary_path is None or on_complete is None:
            return
        try:
            on_complete(summary_path)
        except Exception:  # pragma: no cover - defensive logging in daemon thread.
            logger.exception("Failed to apply background onboarding discovery output.")

    thread = threading.Thread(
        target=_run_and_finalize,
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
    pkm_source = str(getattr(args, "pkm_source", "")).strip().lower()
    profile_links = list(getattr(args, "profile_links", []) or [])
    token_env = str(getattr(args, "token_env", DEFAULT_GIT_TOKEN_ENV)).strip()
    notion_token_env = DEFAULT_NOTION_TOKEN_ENV
    token_username = str(
        getattr(args, "token_username", DEFAULT_TOKEN_USERNAME)
    ).strip()
    if not pkm_source:
        pkm_source = "github" if repo_url else "skip"
    prepare_obsidian_vault_path_env(pkm_source=pkm_source, repo_url=repo_url)
    agent_id = _resolve_agent_id(team_id)
    if agent_id is None:
        logger.warning("Unable to resolve agent_id for onboarding discovery.")

    repo_sync_allowed = pkm_source == "github" and bool(repo_url)
    notion_sync_allowed = pkm_source == "notion"
    if repo_sync_allowed and not _ensure_onboarding_token(token_env):
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
    if notion_sync_allowed and not _ensure_notion_token(notion_token_env):
        print(get_message("onboarding_discovery", "need_notion_token"))
        print(
            get_message(
                "onboarding_discovery",
                "store_notion_token",
                vault_name=VAULT_NAME,
                token_env=notion_token_env,
            )
        )
        if allow_prompt:
            if not _prompt_continue_without_pkm(
                get_message("onboarding_discovery", "pkm_access_unavailable")
            ):
                return None
        notion_sync_allowed = False

    cli_tool = _create_cli_tool()
    if cli_tool is None:
        print(get_message("onboarding_discovery", "cli_tool_unavailable"))
        return None

    profile_summary = _fetch_profile_links(
        cli_tool,
        profile_links,
        agent_id=agent_id,
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
            agent_id=agent_id,
            repo_url=repo_url,
            branch=branch,
            token_env=token_env,
            token_username=token_username,
        )
        if success:
            markdown_summary, pkm_file_excerpts = _summarize_markdown_repo(repo_path)
            if team_id is not None and markdown_summary.strip():
                markers = _store_markdown_memory_entries(
                    team_id=team_id,
                    markdown_summary=markdown_summary,
                    pkm_file_excerpts=pkm_file_excerpts,
                )
                _verify_pkm_memory_import(
                    team_id=team_id,
                    source="obsidian",
                    expected_markers=markers,
                )
        elif allow_prompt:
            if not _prompt_continue_without_pkm(
                get_message("onboarding_discovery", "pkm_sync_failed")
            ):
                return None
    elif notion_sync_allowed:
        print(get_message("onboarding_discovery", "notion_sync_starting"))
        notion_summary, notion_item_summaries, success = _sync_notion_workspace(
            cli_tool=cli_tool,
            agent_id=agent_id,
        )
        if success:
            markdown_summary = notion_summary
            if team_id is not None and markdown_summary.strip():
                markers = _store_notion_memory_entries(
                    team_id=team_id,
                    notion_summary=markdown_summary,
                    notion_item_summaries=notion_item_summaries,
                )
                _verify_pkm_memory_import(
                    team_id=team_id,
                    source="notion",
                    expected_markers=markers,
                )
        elif allow_prompt:
            if not _prompt_continue_without_pkm(
                get_message("onboarding_discovery", "pkm_sync_failed")
            ):
                return None
    summary_text = _render_onboarding_summary(
        user_name=user_name,
        pkm_source=pkm_source,
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


def _ensure_notion_token(token_env: str) -> bool:
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


def prepare_obsidian_vault_path_env(*, pkm_source: str, repo_url: str) -> str | None:
    source = pkm_source.strip().lower()
    normalized_repo = repo_url.strip()
    if source != "github" or not normalized_repo:
        return None
    repo_name = _repo_name_from_url(normalized_repo)
    if not repo_name:
        return None
    vault_path = resolve_data_path("obsidian", repo_name).resolve()
    resolved = str(vault_path)
    os.environ["OBSIDIAN_VAULT_PATH"] = resolved
    return resolved


def _sync_obsidian_repo(
    *,
    cli_tool: CliTool,
    agent_id: str | None,
    repo_url: str,
    branch: str,
    token_env: str,
    token_username: str,
) -> tuple[Path, bool]:
    repo_name = _repo_name_from_url(repo_url)
    dest = resolve_data_path("obsidian", repo_name)
    dest_arg = _container_repo_relative_path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    stop_event = _start_sync_notifier()
    result = _run_cli_tool(
        cli_tool,
        "git-readonly-sync",
        agent_id=agent_id,
        repo=repo_url,
        dest=dest_arg,
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
    os.environ["OBSIDIAN_VAULT_PATH"] = str(dest.resolve())
    return dest, True


def _container_repo_relative_path(path: Path) -> str:
    """
    Convert host paths under repo root into container workspace-relative paths.
    """
    root = get_repo_root() or Path.cwd()
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _sync_notion_workspace(
    *,
    cli_tool: CliTool,
    agent_id: str | None,
) -> tuple[str, list[str], bool]:
    search_body = {
        "page_size": 25,
        "sort": {"direction": "descending", "timestamp": "last_edited_time"},
    }
    result = _run_cli_tool(
        cli_tool,
        "notion",
        agent_id=agent_id,
        method="POST",
        path="/v1/search",
        body=json.dumps(search_body),
        timeout=30,
    )
    if not result.get("success"):
        error = result.get("error") or result.get("stderr") or result.get("raw_output")
        if not error:
            error = f"Unknown error (result={result})" if result else "Unknown error"
        print(get_message("onboarding_discovery", "failed_sync_notion", error=error))
        return "", [], False
    output = result.get("output")
    payload = output.get("response") if isinstance(output, dict) else None
    if not isinstance(payload, dict):
        print(
            get_message(
                "onboarding_discovery",
                "failed_sync_notion",
                error="No response payload.",
            )
        )
        return "", [], False
    results = payload.get("results")
    if not isinstance(results, list):
        print(
            get_message(
                "onboarding_discovery",
                "failed_sync_notion",
                error="No results returned.",
            )
        )
        return "", [], False
    summary, item_summaries = _summarize_notion_results(results)
    return summary, item_summaries, True


def _start_sync_notifier() -> threading.Event:
    stop_event = threading.Event()

    def _notify() -> None:
        while not stop_event.wait(60):
            print(get_message("onboarding_discovery", "pkm_sync_still_running"))

    threading.Thread(target=_notify, daemon=True).start()
    return stop_event


def _summarize_markdown_repo(repo_path: Path) -> tuple[str, list[tuple[str, str]]]:
    file_excerpts, skipped_count = _collect_markdown_repo_file_excerpts(repo_path)
    lines = [f"Markdown files analyzed: {len(file_excerpts)}"]
    for relative_path, excerpt in file_excerpts:
        lines.append(f"\n## {relative_path}")
        if excerpt:
            lines.append(excerpt)
    if skipped_count > 0:
        lines.append(
            f"\nSkipped {skipped_count} markdown files (limit {MARKDOWN_PKM_FILE_LIMIT})."
        )
    return "\n".join(lines), file_excerpts


def _collect_markdown_repo_file_excerpts(
    repo_path: Path,
) -> tuple[list[tuple[str, str]], int]:
    files = sorted(repo_path.rglob("*.md"))
    limited = files[:MARKDOWN_PKM_FILE_LIMIT]
    excerpts: list[tuple[str, str]] = []
    for path in limited:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        excerpt_lines = content.strip().splitlines()[:MARKDOWN_PKM_LINES_PER_FILE]
        excerpt = "\n".join(excerpt_lines).strip()
        excerpts.append((str(path.relative_to(repo_path)), excerpt))
    skipped_count = max(0, len(files) - MARKDOWN_PKM_FILE_LIMIT)
    return excerpts, skipped_count


def _store_markdown_memory_entries(
    *,
    team_id: int,
    markdown_summary: str,
    pkm_file_excerpts: list[tuple[str, str]],
) -> list[str]:
    markers: list[str] = []
    if store_onboarding_memory_entry(
        team_id=team_id,
        content=markdown_summary,
        tags=["onboarding", "pkm"],
        source=MemorySource.IMPORT,
        priority=MemoryPriority.HIGH,
        layer=MemoryLayer.LONG_TERM,
    ):
        markers.append(markdown_summary.splitlines()[0].strip())
    for relative_path, excerpt in pkm_file_excerpts:
        if not excerpt:
            continue
        content = f"PKM file: {relative_path}\n\n{excerpt}"
        if not store_onboarding_memory_entry(
            team_id=team_id,
            content=content,
            tags=["onboarding", "pkm", "pkm_file"],
            source=MemorySource.IMPORT,
            priority=MemoryPriority.HIGH,
            layer=MemoryLayer.LONG_TERM,
        ):
            continue
        markers.append(f"PKM file: {relative_path}")
    return markers


def _summarize_notion_results(results: list[dict[str, Any]]) -> tuple[str, list[str]]:
    lines = [f"Notion items analyzed: {len(results)}"]
    item_summaries: list[str] = []
    for item in results:
        title = _extract_notion_title(item)
        url = item.get("url") if isinstance(item.get("url"), str) else ""
        object_type = (
            item.get("object") if isinstance(item.get("object"), str) else "item"
        )
        last_edited = (
            item.get("last_edited_time")
            if isinstance(item.get("last_edited_time"), str)
            else ""
        )
        suffix = f" ({last_edited})" if last_edited else ""
        url_text = f" {url}" if url else ""
        item_line = f"[{object_type}] {title}{suffix}{url_text}"
        lines.append(f"- {item_line}")
        item_summaries.append(f"Notion item: {item_line}")
    return "\n".join(lines), item_summaries


def _store_notion_memory_entries(
    *,
    team_id: int,
    notion_summary: str,
    notion_item_summaries: list[str],
) -> list[str]:
    markers: list[str] = []
    if store_onboarding_memory_entry(
        team_id=team_id,
        content=notion_summary,
        tags=["onboarding", "pkm"],
        source=MemorySource.IMPORT,
        priority=MemoryPriority.HIGH,
        layer=MemoryLayer.LONG_TERM,
    ):
        markers.append(notion_summary.splitlines()[0].strip())
    for item_summary in notion_item_summaries:
        if not item_summary.strip():
            continue
        normalized_item_summary = item_summary.strip()
        if not store_onboarding_memory_entry(
            team_id=team_id,
            content=normalized_item_summary,
            tags=["onboarding", "pkm", "pkm_notion_item"],
            source=MemorySource.IMPORT,
            priority=MemoryPriority.HIGH,
            layer=MemoryLayer.LONG_TERM,
        ):
            continue
        markers.append(normalized_item_summary)
    return markers


def _verify_pkm_memory_import(
    *,
    team_id: int,
    source: str,
    expected_markers: list[str],
) -> None:
    normalized_markers = [
        marker.strip() for marker in expected_markers if marker.strip()
    ]
    if not normalized_markers:
        return
    memory_contents = fetch_onboarding_memory_contents(team_id)
    if not memory_contents:
        print(
            "PKM memory verification "
            f"({source}): unable to read onboarding memory entries."
        )
        return
    matched = 0
    missing: list[str] = []
    for marker in normalized_markers:
        if any(marker in content for content in memory_contents):
            matched += 1
        else:
            missing.append(marker)
    print(
        f"PKM memory verification ({source}): "
        f"{matched}/{len(normalized_markers)} entries verified."
    )
    if not missing:
        return
    preview = ", ".join(missing[:3])
    if len(missing) > 3:
        preview = f"{preview}, ..."
    print(f"PKM memory verification missing markers: {preview}")


def _extract_notion_title(item: dict[str, Any]) -> str:
    if item.get("object") == "database":
        title = item.get("title")
        return _join_notion_title_parts(title) or "Untitled database"
    if item.get("object") == "page":
        properties = item.get("properties")
        if isinstance(properties, dict):
            for value in properties.values():
                if not isinstance(value, dict):
                    continue
                if value.get("type") != "title":
                    continue
                return _join_notion_title_parts(value.get("title")) or "Untitled page"
    return "Untitled item"


def _join_notion_title_parts(parts: Any) -> str:
    if not isinstance(parts, list):
        return ""
    texts = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = part.get("plain_text")
        if isinstance(text, str) and text:
            texts.append(text)
    return "".join(texts).strip()


def _fetch_profile_links(
    cli_tool: CliTool,
    links: list[str],
    agent_id: str | None,
    on_entry: Callable[[str, str], None] | None = None,
) -> str:
    if not links:
        return "No profile links provided."
    sections = []
    for link in links:
        result = _run_cli_tool(cli_tool, "web-fetch", agent_id=agent_id, url=link)
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
    pkm_source: str,
    repo_url: str,
    profile_links: list[str],
    markdown_summary: str,
    profile_summary: str,
) -> str:
    links_text = "\n".join(profile_links) if profile_links else "None"
    repo_line = repo_url if repo_url else "None"
    return "\n".join(
        [
            "# Onboarding Summary",
            f"User: {user_name}",
            f"PKM: {pkm_source}",
            f"Repo: {repo_line}",
            "Profile links:",
            links_text,
            "",
            "# PKM Notes",
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


def _resolve_agent_id(team_id: int | None) -> str | None:
    if team_id is None:
        return None
    system4 = get_system_by_type(team_id, SystemType.INTELLIGENCE)
    if system4 is None:
        return None
    return system4.agent_id_str


def build_onboarding_prompt(summary_path: Path, summary_text: str) -> str:
    prompt_summary = summary_text
    if len(prompt_summary) > ONBOARDING_PROMPT_SUMMARY_CHAR_LIMIT:
        prompt_summary = (
            prompt_summary[:ONBOARDING_PROMPT_SUMMARY_CHAR_LIMIT].rstrip()
            + "\n\n[Summary truncated for prompt. See summary file for full content.]"
        )
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
            prompt_summary,
        ]
    )


def build_onboarding_interview_prompt(
    *,
    user_name: str,
    pkm_source: str,
    repo_url: str,
    profile_links: list[str],
    first_question: str,
) -> str:
    links_text = "\n".join(profile_links) if profile_links else "None"
    repo_line = repo_url if repo_url else "None"
    return "\n".join(
        [
            "## ONBOARDING INTERVIEW",
            "Start the onboarding interview now.",
            f"The first question has already been sent: {first_question}",
            "Wait for the user response before sending the next question.",
            "Ask no more than 10 questions total in this onboarding interview,",
            "including the first question that was already sent.",
            "Before each question, check memory for new onboarding entries.",
            "Log user responses into memory as you learn them.",
            "If the user mentions a specific company, city, product, or industry",
            "that is not in memory, trigger background web research and store",
            "the results in memory for future questions.",
            "",
            f"User: {user_name}",
            f"PKM: {pkm_source}",
            f"Repo: {repo_line}",
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
    agent_id: str | None,
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
                    tool_name,
                    agent_id=agent_id,
                    timeout_seconds=timeout_seconds,
                    **kwargs,
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
