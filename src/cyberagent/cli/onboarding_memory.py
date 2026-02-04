from __future__ import annotations

from pathlib import Path

from src.cyberagent.db.models.system import get_system_by_type
from src.cyberagent.memory.config import (
    build_memory_registry,
    load_memory_backend_config,
)
from src.cyberagent.memory.crud import (
    MemoryActorContext,
    MemoryCreateRequest,
    MemoryCrudService,
)
from src.cyberagent.memory.models import (
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.cli.message_catalog import get_message
from src.enums import SystemType


def store_onboarding_memory(team_id: int, summary_path: Path | None) -> None:
    if summary_path is None or not summary_path.exists():
        return
    try:
        summary_text = summary_path.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if not summary_text:
        return

    actor = _build_system4_actor(team_id)
    if actor is None:
        return
    service = _build_memory_service()
    request = MemoryCreateRequest(
        content=summary_text,
        namespace="user",
        scope=MemoryScope.GLOBAL,
        tags=["onboarding", "user_profile"],
        priority=MemoryPriority.HIGH,
        source=MemorySource.IMPORT,
        confidence=0.7,
        expires_at=None,
        layer=MemoryLayer.LONG_TERM,
        owner_agent_id=actor.agent_id,
    )
    try:
        service.create_entries(actor=actor, requests=[request])
    except (PermissionError, ValueError):
        print(get_message("onboarding_memory", "unable_store_summary"))


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
) -> None:
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
        return
    actor = _build_system4_actor(team_id)
    if actor is None:
        return
    service = _build_memory_service()
    request = MemoryCreateRequest(
        content=content.strip(),
        namespace=namespace,
        scope=MemoryScope.GLOBAL,
        tags=tags,
        priority=priority,
        source=source,
        confidence=confidence,
        expires_at=None,
        layer=layer,
        owner_agent_id=actor.agent_id,
    )
    try:
        service.create_entries(actor=actor, requests=[request])
    except (PermissionError, ValueError):
        print(get_message("onboarding_memory", "unable_store_summary"))


def _build_system4_actor(team_id: int) -> MemoryActorContext | None:
    system4 = get_system_by_type(team_id, SystemType.INTELLIGENCE)
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
