from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

from autogen_core import AgentId, CancellationToken

from src.cyberagent.db.models.system import get_system_by_type
from src.cyberagent.memory.config import (
    build_memory_registry,
    load_memory_backend_config,
)
from src.cyberagent.memory.crud import MemoryActorContext, MemoryCrudService
from src.cyberagent.memory.models import (
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.tools.memory_crud import (
    MemoryCrudArgs,
    MemoryCrudResponse,
    MemoryCrudTool,
)
from src.cyberagent.cli.message_catalog import get_message
from src.enums import SystemType


def store_onboarding_memory(team_id: int, summary_path: Path | None) -> bool:
    if summary_path is None or not summary_path.exists():
        return False
    try:
        summary_text = summary_path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not summary_text:
        return False

    actor = _build_system4_actor(team_id)
    if actor is None:
        return False
    tool = _build_memory_tool(actor)
    args = MemoryCrudArgs(
        action="create",
        scope=MemoryScope.GLOBAL.value,
        namespace="user",
        items=[
            {
                "content": summary_text,
                "tags": ["onboarding", "user_profile"],
                "priority": MemoryPriority.HIGH.value,
                "source": MemorySource.IMPORT.value,
                "confidence": 0.7,
                "expires_at": None,
                "layer": MemoryLayer.LONG_TERM.value,
                "owner_agent_id": actor.agent_id,
            }
        ],
    )
    response = _run_memory_tool(tool, args)
    if response.errors:
        print(get_message("onboarding_memory", "unable_store_summary"))
        return False
    return True


def store_onboarding_memory_entry(
    *,
    team_id: int,
    content: str,
    tags: list[str],
    source: MemorySource,
    priority: MemoryPriority,
    layer: MemoryLayer,
    namespace: str = "user",
    confidence: float = 0.6,
) -> bool:
    """
    Store an incremental onboarding memory entry for live interview enrichment.

    Args:
        team_id: Team ID to store the entry under.
        content: Memory content payload.
        tags: Tags describing the entry.
        source: Memory source classification.
        priority: Memory priority.
        layer: Memory layer.
        namespace: Memory namespace.
        confidence: Confidence level between 0 and 1.
    """
    if not content.strip():
        return False
    actor = _build_system4_actor(team_id)
    if actor is None:
        return False
    tool = _build_memory_tool(actor)
    args = MemoryCrudArgs(
        action="create",
        scope=MemoryScope.GLOBAL.value,
        namespace=namespace,
        items=[
            {
                "content": content.strip(),
                "tags": tags,
                "priority": priority.value,
                "source": source.value,
                "confidence": confidence,
                "expires_at": None,
                "layer": layer.value,
                "owner_agent_id": actor.agent_id,
            }
        ],
    )
    response = _run_memory_tool(tool, args)
    if response.errors:
        print(get_message("onboarding_memory", "unable_store_summary"))
        return False
    return True


def fetch_onboarding_memory_contents(
    team_id: int,
    *,
    namespace: str = "user",
    limit: int = 500,
) -> list[str]:
    """
    List onboarding memory content currently stored in global/user namespace.

    Args:
        team_id: Team identifier.
        namespace: Memory namespace to inspect.
        limit: Maximum number of entries to inspect.
    """
    if limit <= 0:
        return []
    actor = _build_system4_actor(team_id)
    if actor is None:
        return []
    tool = _build_memory_tool(actor)
    contents: list[str] = []
    cursor: str | None = None
    while len(contents) < limit:
        batch_limit = min(100, limit - len(contents))
        args = MemoryCrudArgs(
            action="list",
            scope=MemoryScope.GLOBAL.value,
            namespace=namespace,
            limit=batch_limit,
            cursor=cursor,
        )
        response = _run_memory_tool(tool, args)
        if response.errors:
            return contents
        for item in response.items:
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                contents.append(content)
        if not response.has_more or not response.next_cursor:
            break
        cursor = response.next_cursor
    return contents


def _build_system4_actor(team_id: int) -> MemoryActorContext | None:
    try:
        system4 = get_system_by_type(team_id, SystemType.INTELLIGENCE)
    except ValueError:
        return None
    if system4 is None:
        return None
    return MemoryActorContext(
        agent_id=system4.agent_id_str,
        system_id=system4.id,
        team_id=team_id,
        system_type=system4.type,
    )


def _build_memory_service() -> MemoryCrudService:
    config = load_memory_backend_config()
    registry = build_memory_registry(config)
    return MemoryCrudService(registry=registry)


def _build_memory_tool(actor: MemoryActorContext) -> MemoryCrudTool:
    agent_id = AgentId.from_str(actor.agent_id)
    return MemoryCrudTool(
        agent_id, actor_context=actor, service=_build_memory_service()
    )


def _run_memory_tool(tool: MemoryCrudTool, args: MemoryCrudArgs) -> MemoryCrudResponse:
    return _run_async(tool.run(args, CancellationToken()))


_T = TypeVar("_T")


def _run_async(coro: Coroutine[Any, Any, _T]) -> _T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("Cannot run memory_crud tool inside an active event loop.")
