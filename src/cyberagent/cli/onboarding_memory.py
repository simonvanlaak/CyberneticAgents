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

    system4 = get_system_by_type(team_id, SystemType.INTELLIGENCE)
    if system4 is None:
        return

    actor = MemoryActorContext(
        agent_id=system4.agent_id_str,
        system_id=system4.id,
        team_id=team_id,
        system_type=system4.type,
    )
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
        owner_agent_id=system4.agent_id_str,
    )
    try:
        service.create_entries(actor=actor, requests=[request])
    except (PermissionError, ValueError):
        print(get_message("onboarding_memory", "unable_store_summary"))


def _build_memory_service() -> MemoryCrudService:
    config = load_memory_backend_config()
    registry = build_memory_registry(config)
    return MemoryCrudService(registry=registry)
