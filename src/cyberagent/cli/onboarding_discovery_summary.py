from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading
from typing import Any, Callable

from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.core.paths import get_repo_root
from src.cyberagent.cli.onboarding_constants import ONBOARDING_SUMMARY_DIR
from src.cyberagent.cli.onboarding_memory import (
    fetch_onboarding_memory_contents,
    store_onboarding_memory_entry,
)
from src.cyberagent.db.models.system import get_system_by_type
from src.cyberagent.memory.models import MemoryLayer, MemoryPriority, MemorySource
from src.cyberagent.tools.cli_executor.cli_tool import CliTool
from src.enums import SystemType

ONBOARDING_PROMPT_SUMMARY_CHAR_LIMIT = 12000


def summarize_notion_results(results: list[dict[str, Any]]) -> tuple[str, list[str]]:
    lines = [f"Notion items analyzed: {len(results)}"]
    item_summaries: list[str] = []
    for item in results:
        title = extract_notion_title(item)
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


def store_notion_memory_entries(
    *,
    team_id: int,
    notion_summary: str,
    notion_item_summaries: list[str],
    store_entry: Callable[..., bool | None] = store_onboarding_memory_entry,
) -> list[str]:
    markers: list[str] = []
    if store_entry(
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
        if not store_entry(
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


def verify_pkm_memory_import(
    *,
    team_id: int,
    source: str,
    expected_markers: list[str],
    fetch_memory_contents: Callable[
        [int], list[str]
    ] = fetch_onboarding_memory_contents,
) -> None:
    normalized_markers = [
        marker.strip() for marker in expected_markers if marker.strip()
    ]
    if not normalized_markers:
        return
    memory_contents = fetch_memory_contents(team_id)
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


def extract_notion_title(item: dict[str, Any]) -> str:
    if item.get("object") == "database":
        title = item.get("title")
        return join_notion_title_parts(title) or "Untitled database"
    if item.get("object") == "page":
        properties = item.get("properties")
        if isinstance(properties, dict):
            for value in properties.values():
                if not isinstance(value, dict):
                    continue
                if value.get("type") != "title":
                    continue
                return join_notion_title_parts(value.get("title")) or "Untitled page"
    return "Untitled item"


def join_notion_title_parts(parts: Any) -> str:
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


def fetch_profile_links(
    cli_tool: CliTool,
    links: list[str],
    agent_id: str | None,
    run_cli_tool: Callable[..., dict[str, object]],
    on_entry: Callable[[str, str], None] | None = None,
) -> str:
    if not links:
        return "No profile links provided."
    sections = []
    for link in links:
        result = run_cli_tool(cli_tool, "web-fetch", agent_id=agent_id, url=link)
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


def build_profile_link_entry_writer(
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


def render_onboarding_summary(
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


def resolve_agent_id(team_id: int | None) -> str | None:
    if team_id is None:
        return None
    system4 = get_system_by_type(team_id, SystemType.INTELLIGENCE)
    if system4 is None:
        return None
    return system4.agent_id_str


def container_repo_relative_path(path: Path) -> str:
    root = get_repo_root() or Path.cwd()
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def start_sync_notifier() -> threading.Event:
    stop_event = threading.Event()

    def _notify() -> None:
        while not stop_event.wait(60):
            print(get_message("onboarding_discovery", "pkm_sync_still_running"))

    threading.Thread(target=_notify, daemon=True).start()
    return stop_event


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


def write_onboarding_summary(summary_text: str) -> Path | None:
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


def prompt_continue_without_pkm(reason: str) -> bool:
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
