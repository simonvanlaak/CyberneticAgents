from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
from pathlib import Path
import subprocess
import threading
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse

from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.onboarding_auto_execute import (
    auto_execute_onboarding_sop_if_configured,
)
from src.cyberagent.cli.onboarding_constants import (
    DEFAULT_GIT_TOKEN_ENV,
    DEFAULT_NOTION_TOKEN_ENV,
    DEFAULT_TOKEN_USERNAME,
    GIT_SYNC_TIMEOUT_SECONDS,
)
from src.cyberagent.cli.onboarding_discovery_summary import (
    ONBOARDING_PROMPT_SUMMARY_CHAR_LIMIT as _ONBOARDING_PROMPT_SUMMARY_CHAR_LIMIT,
    build_onboarding_interview_prompt as _build_onboarding_interview_prompt,
    build_onboarding_prompt,
    build_profile_link_entry_writer as _build_profile_link_entry_writer,
    container_repo_relative_path as _container_repo_relative_path,
    fetch_profile_links as _fetch_profile_links_impl,
    prompt_continue_without_pkm as _prompt_continue_without_pkm,
    render_onboarding_summary as _render_onboarding_summary,
    start_sync_notifier as _start_sync_notifier,
    store_notion_memory_entries as _store_notion_memory_entries_impl,
    summarize_notion_results as _summarize_notion_results,
    verify_pkm_memory_import as _verify_pkm_memory_import_impl,
    write_onboarding_summary as _write_onboarding_summary,
)
from src.cyberagent.cli.onboarding_discovery_sync import (
    is_interpreter_shutdown_error as _is_interpreter_shutdown_error,
    sync_obsidian_repo_with_git as _sync_obsidian_repo_with_git,
)
from src.cyberagent.cli.onboarding_memory import (
    fetch_onboarding_memory_contents,
    store_onboarding_memory,
    store_onboarding_memory_entry,
)
from src.cyberagent.cli.onboarding_secrets import (
    VAULT_NAME,
    check_onepassword_cli_access,
    has_onepassword_auth,
    load_secret_from_1password_with_error,
)
from src.cyberagent.cli.suggestion_queue import enqueue_suggestion
from src.cyberagent.core.paths import resolve_data_path
from src.cyberagent.db.models.system import get_system_by_type
from src.cyberagent.memory.models import MemoryLayer, MemoryPriority, MemorySource
from src.cyberagent.tools.cli_executor.cli_tool import CliTool
from src.cyberagent.tools.cli_executor.factory import create_cli_executor
from src.enums import SystemType

logger = logging.getLogger(__name__)
MARKDOWN_PKM_FILE_LIMIT = 1000
MARKDOWN_PKM_LINES_PER_FILE = 20
ONBOARDING_PROMPT_SUMMARY_CHAR_LIMIT = _ONBOARDING_PROMPT_SUMMARY_CHAR_LIMIT
_auto_execute_onboarding_sop_if_configured = auto_execute_onboarding_sop_if_configured
build_onboarding_interview_prompt = _build_onboarding_interview_prompt


def _store_notion_memory_entries(**kwargs: object) -> list[str]:
    return _store_notion_memory_entries_impl(
        store_entry=store_onboarding_memory_entry,
        **kwargs,
    )


def _verify_pkm_memory_import(**kwargs: object) -> None:
    _verify_pkm_memory_import_impl(
        fetch_memory_contents=fetch_onboarding_memory_contents,
        **kwargs,
    )


def run_discovery_onboarding(args: object, team_id: int | None = None) -> Path | None:
    return _run_discovery_pipeline(
        args, team_id=team_id, allow_prompt=True, enqueue_prompt=True
    )


def start_discovery_background(
    args: object,
    team_id: int,
    on_complete: Callable[[Path], None] | None = None,
) -> None:
    if os.environ.get("CYBERAGENT_DISABLE_BACKGROUND_DISCOVERY"):
        logger.info("Background discovery disabled via env override.")
        return

    completion_callback = on_complete or _default_background_on_complete(team_id)

    def _run_and_finalize() -> None:
        summary_path = _run_discovery_pipeline(
            args=args,
            team_id=team_id,
            allow_prompt=False,
            enqueue_prompt=True,
        )
        if summary_path is None or completion_callback is None:
            return
        try:
            completion_callback(summary_path)
        except Exception:  # pragma: no cover - defensive logging in daemon thread.
            logger.exception("Failed to apply background onboarding discovery output.")

    thread = threading.Thread(target=_run_and_finalize, daemon=False)
    thread.start()


def _default_background_on_complete(team_id: int) -> Callable[[Path], None] | None:
    try:
        from src.cyberagent.cli.onboarding_defaults import (
            get_default_strategy_name,
            load_root_team_defaults,
        )
        from src.cyberagent.cli.onboarding_output import apply_onboarding_output
    except Exception:  # pragma: no cover - import errors are environment-specific.
        logger.exception("Unable to initialize background onboarding apply callback.")
        return None

    team_defaults = load_root_team_defaults()
    strategy_name = get_default_strategy_name(team_defaults)

    def _apply(summary_path: Path) -> None:
        apply_onboarding_output(
            team_id=team_id,
            summary_path=summary_path,
            onboarding_strategy_name=strategy_name,
        )

    return _apply


def _resolve_agent_id(team_id: int | None) -> str | None:
    system4 = (
        None
        if team_id is None
        else get_system_by_type(team_id, SystemType.INTELLIGENCE)
    )
    return system4.agent_id_str if system4 is not None else None


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
        _auto_execute_onboarding_sop_if_configured(team_id)
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
    last_error: str | None = None
    for attempt in range(2):
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
        if result.get("success"):
            os.environ["OBSIDIAN_VAULT_PATH"] = str(dest.resolve())
            return dest, True

        error_obj = (
            result.get("error") or result.get("stderr") or result.get("raw_output")
        )
        if error_obj:
            last_error = str(error_obj)
        else:
            last_error = (
                f"Unknown error (result={result})" if result else "Unknown error"
            )
        if attempt == 0 and _is_interpreter_shutdown_error(last_error):
            logger.warning(
                "PKM repo sync hit interpreter-shutdown scheduling race. Retrying once."
            )
            continue
        if _is_interpreter_shutdown_error(last_error):
            logger.warning(
                "PKM repo sync failed after retry due to interpreter-shutdown race. "
                "Falling back to direct git sync."
            )
            fallback_success, fallback_error = _sync_obsidian_repo_with_git(
                repo_url=repo_url,
                branch=branch,
                dest=dest,
                token_env=token_env,
                token_username=token_username,
            )
            if fallback_success:
                os.environ["OBSIDIAN_VAULT_PATH"] = str(dest.resolve())
                return dest, True
            if fallback_error:
                last_error = fallback_error
        break

    error_text = last_error or "Unknown error"
    print(get_message("onboarding_discovery", "failed_sync_repo", error=error_text))
    return dest, False


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


def _fetch_profile_links(
    cli_tool: CliTool,
    links: list[str],
    agent_id: str | None,
    on_entry: Callable[[str, str], None] | None = None,
) -> str:
    return _fetch_profile_links_impl(
        cli_tool, links, agent_id, run_cli_tool=_run_cli_tool, on_entry=on_entry
    )


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
