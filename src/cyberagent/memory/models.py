"""Memory domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Sequence


class MemoryScope(str, Enum):
    """Memory scope boundaries."""

    AGENT = "agent"
    TEAM = "team"
    GLOBAL = "global"


class MemoryPriority(str, Enum):
    """Memory priority levels for retrieval and pruning."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MemorySource(str, Enum):
    """Origin for memory entries."""

    REFLECTION = "reflection"
    MANUAL = "manual"
    TOOL = "tool"
    IMPORT = "import"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class MemoryEntry:
    """Single memory record with audit-friendly metadata."""

    id: str
    scope: MemoryScope
    namespace: str
    owner_agent_id: str
    content: str
    priority: MemoryPriority
    created_at: datetime
    updated_at: datetime | None
    source: MemorySource
    confidence: float
    tags: list[str] = field(default_factory=list)
    expires_at: datetime | None = None
    is_conflict: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.tags is None:
            self.tags = []


@dataclass(slots=True)
class MemoryListResult:
    """Cursor-paginated list of memory entries."""

    items: Sequence[MemoryEntry]
    next_cursor: str | None
    has_more: bool

    def __post_init__(self) -> None:
        if self.has_more and not self.next_cursor:
            raise ValueError("next_cursor required when has_more is True")


@dataclass(slots=True)
class MemoryQuery:
    """Query parameters for memory retrieval."""

    text: str | None
    scope: MemoryScope
    namespace: str
    limit: int
    cursor: str | None = None
    tags: Sequence[str] | None = None
    owner_agent_id: str | None = None


@dataclass(slots=True)
class MemoryAuditEvent:
    """Audit event for memory CRUD actions."""

    action: str
    actor_id: str
    scope: MemoryScope
    namespace: str
    resource_id: str
    success: bool
    details: dict[str, str]
    timestamp: datetime = field(default_factory=_utc_now)
