"""Memory CRUD tool for agent skill execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
from typing import Any

from autogen_core import AgentId, CancellationToken
from autogen_core.tools import BaseTool
from pydantic import BaseModel

from src.cyberagent.db.models.system import get_system_from_agent_id
from src.cyberagent.memory.config import (
    build_memory_registry,
    load_memory_backend_config,
)
from src.cyberagent.memory.crud import (
    MemoryActorContext,
    MemoryConflictError,
    MemoryCreateRequest,
    MemoryCrudService,
    MemoryDeleteRequest,
    MemoryReadRequest,
    MemoryUpdateRequest,
)
from src.cyberagent.memory.observability import (
    LoggingMemoryAuditSink,
    build_memory_metrics,
)
from src.cyberagent.memory.models import (
    MemoryEntry,
    MemoryLayer,
    MemoryPriority,
    MemoryScope,
    MemorySource,
)
from src.cyberagent.services import systems as systems_service
from src.enums import SystemType

MAX_BULK_ITEMS = 10
SKILL_NAME = "memory_crud"

logger = logging.getLogger(__name__)


class MemoryCrudArgs(BaseModel):
    action: str
    scope: str | None = None
    namespace: str | None = None
    items: list[dict[str, Any]] | None = None
    cursor: str | None = None
    limit: int | None = None
    layer: str | None = None


class MemoryCrudError(BaseModel):
    code: str
    message: str
    details: dict[str, str] | None = None


class MemoryCrudResponse(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: str | None
    has_more: bool
    errors: list[MemoryCrudError]


@dataclass(slots=True)
class _ResponseBuilder:
    items: list[dict[str, Any]]
    next_cursor: str | None = None
    has_more: bool = False
    errors: list[MemoryCrudError] | None = None

    def add_error(
        self, code: str, message: str, details: dict[str, str] | None = None
    ) -> None:
        if self.errors is None:
            self.errors = []
        self.errors.append(MemoryCrudError(code=code, message=message, details=details))

    def build(self) -> MemoryCrudResponse:
        return MemoryCrudResponse(
            items=self.items,
            next_cursor=self.next_cursor,
            has_more=self.has_more,
            errors=self.errors or [],
        )


class MemoryCrudTool(BaseTool):
    """Tool wrapper for memory CRUD operations."""

    def __init__(
        self,
        agent_id: AgentId,
        *,
        service: MemoryCrudService | None = None,
        actor_context: MemoryActorContext | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._service = service or _build_memory_service()
        self._actor_context = actor_context or _build_actor_context(agent_id)
        super().__init__(
            name="memory_crud",
            description="Create, read, update, delete, list, or promote memory entries.",
            return_type=MemoryCrudResponse,
            args_type=MemoryCrudArgs,
        )

    async def run(
        self, args: MemoryCrudArgs, cancellation_token: CancellationToken
    ) -> MemoryCrudResponse:
        del cancellation_token
        self._log_invocation(args)
        action = args.action.lower().strip()
        builder = _ResponseBuilder(items=[])
        if not self._check_permission(builder):
            return builder.build()
        if action == "list":
            return self._handle_list(args, builder)
        if action == "create":
            return self._handle_create(args, builder)
        if action == "read":
            return self._handle_read(args, builder)
        if action == "update":
            return self._handle_update(args, builder)
        if action == "delete":
            return self._handle_delete(args, builder)
        if action == "promote":
            return self._handle_promote(args, builder)
        builder.add_error("INVALID_PARAMS", f"Unknown action '{args.action}'.")
        return builder.build()

    def _log_invocation(self, args: MemoryCrudArgs) -> None:
        payload = json.dumps(
            {
                "caller_agent_id": self._actor_context.agent_id,
                "scope": args.scope,
                "namespace": args.namespace,
                "action": args.action,
            }
        )
        logger.info("memory_crud_invocation %s", payload)

    def _check_permission(self, builder: _ResponseBuilder) -> bool:
        allowed, reason = systems_service.can_execute_skill(
            self._actor_context.system_id, SKILL_NAME
        )
        if allowed:
            return True
        details = {"failed_rule_category": reason} if reason else None
        builder.add_error(
            "FORBIDDEN", f"Skill '{SKILL_NAME}' is not permitted.", details
        )
        return False

    def _handle_list(
        self, args: MemoryCrudArgs, builder: _ResponseBuilder
    ) -> MemoryCrudResponse:
        try:
            scope = _parse_scope(args.scope)
            layer = _parse_layer(args.layer) if args.layer else None
            result = self._service.list_entries(
                actor=self._actor_context,
                scope=scope,
                namespace=args.namespace,
                limit=args.limit,
                cursor=args.cursor,
                layer=layer,
            )
            builder.items = [_entry_to_payload(entry) for entry in result.items]
            builder.next_cursor = result.next_cursor
            builder.has_more = result.has_more
            return builder.build()
        except ValueError as exc:
            builder.add_error("INVALID_PARAMS", str(exc))
            return builder.build()
        except PermissionError as exc:
            builder.add_error("FORBIDDEN", str(exc))
            return builder.build()

    def _handle_create(
        self, args: MemoryCrudArgs, builder: _ResponseBuilder
    ) -> MemoryCrudResponse:
        items = args.items or []
        if len(items) > MAX_BULK_ITEMS:
            builder.add_error(
                "INVALID_PARAMS",
                f"bulk memory CRUD limit exceeded (max {MAX_BULK_ITEMS})",
            )
            return builder.build()
        try:
            scope = _parse_scope(args.scope)
        except ValueError as exc:
            builder.add_error("INVALID_PARAMS", str(exc))
            return builder.build()
        for item in items:
            try:
                request = _build_create_request(args.namespace, scope, item)
            except ValueError as exc:
                builder.add_error("INVALID_PARAMS", str(exc))
                continue
            if isinstance(request, MemoryCrudError):
                builder.add_error(request.code, request.message, request.details)
                continue
            try:
                created = self._service.create_entries(
                    actor=self._actor_context, requests=[request]
                )
                builder.items.extend(_entry_to_payload(entry) for entry in created)
            except PermissionError as exc:
                builder.add_error("FORBIDDEN", str(exc))
            except ValueError as exc:
                builder.add_error("INVALID_PARAMS", str(exc))
        return builder.build()

    def _handle_read(
        self, args: MemoryCrudArgs, builder: _ResponseBuilder
    ) -> MemoryCrudResponse:
        items = args.items or []
        if len(items) > MAX_BULK_ITEMS:
            builder.add_error(
                "INVALID_PARAMS",
                f"bulk memory CRUD limit exceeded (max {MAX_BULK_ITEMS})",
            )
            return builder.build()
        if not items:
            builder.add_error("INVALID_PARAMS", "read requires items with entry_id.")
            return builder.build()
        try:
            scope = _parse_scope(args.scope)
        except ValueError as exc:
            builder.add_error("INVALID_PARAMS", str(exc))
            return builder.build()
        for item in items:
            entry_id = _item_str(item, "entry_id")
            if not entry_id:
                builder.add_error("INVALID_PARAMS", "entry_id is required for read.")
                continue
            try:
                request = MemoryReadRequest(
                    entry_id=entry_id,
                    scope=scope,
                    namespace=args.namespace,
                    target_team_id=_item_int(item, "target_team_id"),
                )
            except ValueError as exc:
                builder.add_error("INVALID_PARAMS", str(exc))
                continue
            try:
                entry = self._service.read_entry(
                    actor=self._actor_context, request=request
                )
            except PermissionError as exc:
                builder.add_error("FORBIDDEN", str(exc))
                continue
            if entry is None:
                builder.add_error("NOT_FOUND", f"memory entry not found: {entry_id}")
                continue
            builder.items.append(_entry_to_payload(entry))
        return builder.build()

    def _handle_update(
        self, args: MemoryCrudArgs, builder: _ResponseBuilder
    ) -> MemoryCrudResponse:
        items = args.items or []
        if len(items) > MAX_BULK_ITEMS:
            builder.add_error(
                "INVALID_PARAMS",
                f"bulk memory CRUD limit exceeded (max {MAX_BULK_ITEMS})",
            )
            return builder.build()
        try:
            scope = _parse_scope(args.scope)
        except ValueError as exc:
            builder.add_error("INVALID_PARAMS", str(exc))
            return builder.build()
        for item in items:
            entry_id = _item_str(item, "entry_id")
            if not entry_id:
                builder.add_error("INVALID_PARAMS", "entry_id is required for update.")
                continue
            try:
                request = MemoryUpdateRequest(
                    entry_id=entry_id,
                    scope=scope,
                    namespace=args.namespace,
                    content=_item_str(item, "content"),
                    tags=_item_list(item, "tags"),
                    priority=_parse_priority(item.get("priority")),
                    confidence=_item_float(item, "confidence"),
                    expires_at=_parse_datetime(item.get("expires_at")),
                    layer=_parse_layer(item.get("layer")),
                    if_match=_item_str(item, "if_match"),
                    target_team_id=_item_int(item, "target_team_id"),
                )
            except ValueError as exc:
                builder.add_error("INVALID_PARAMS", str(exc))
                continue
            try:
                updated = self._service.update_entries(
                    actor=self._actor_context, requests=[request]
                )
                builder.items.extend(_entry_to_payload(entry) for entry in updated)
            except NotImplementedError as exc:
                builder.add_error("NOT_IMPLEMENTED", str(exc))
            except MemoryConflictError as exc:
                builder.add_error(
                    "CONFLICT",
                    str(exc),
                    {
                        "conflict_of": exc.entry_id,
                        "conflict_entry": exc.conflict_entry.id,
                    },
                )
            except PermissionError as exc:
                builder.add_error("FORBIDDEN", str(exc))
            except ValueError as exc:
                message = str(exc)
                code = "NOT_FOUND" if "not found" in message else "INVALID_PARAMS"
                builder.add_error(code, message)
        return builder.build()

    def _handle_delete(
        self, args: MemoryCrudArgs, builder: _ResponseBuilder
    ) -> MemoryCrudResponse:
        items = args.items or []
        if len(items) > MAX_BULK_ITEMS:
            builder.add_error(
                "INVALID_PARAMS",
                f"bulk memory CRUD limit exceeded (max {MAX_BULK_ITEMS})",
            )
            return builder.build()
        try:
            scope = _parse_scope(args.scope)
        except ValueError as exc:
            builder.add_error("INVALID_PARAMS", str(exc))
            return builder.build()
        for item in items:
            entry_id = _item_str(item, "entry_id")
            if not entry_id:
                builder.add_error("INVALID_PARAMS", "entry_id is required for delete.")
                continue
            try:
                request = MemoryDeleteRequest(
                    entry_id=entry_id,
                    scope=scope,
                    namespace=args.namespace,
                    if_match=_item_str(item, "if_match"),
                    target_team_id=_item_int(item, "target_team_id"),
                )
            except ValueError as exc:
                builder.add_error("INVALID_PARAMS", str(exc))
                continue
            try:
                results = self._service.delete_entries(
                    actor=self._actor_context, requests=[request]
                )
                builder.items.append({"entry_id": entry_id, "deleted": results[0]})
            except NotImplementedError as exc:
                builder.add_error("NOT_IMPLEMENTED", str(exc))
            except MemoryConflictError as exc:
                builder.add_error(
                    "CONFLICT",
                    str(exc),
                    {
                        "conflict_of": exc.entry_id,
                        "conflict_entry": exc.conflict_entry.id,
                    },
                )
            except PermissionError as exc:
                builder.add_error("FORBIDDEN", str(exc))
            except ValueError as exc:
                message = str(exc)
                code = "NOT_FOUND" if "not found" in message else "INVALID_PARAMS"
                builder.add_error(code, message)
        return builder.build()

    def _handle_promote(
        self, args: MemoryCrudArgs, builder: _ResponseBuilder
    ) -> MemoryCrudResponse:
        items = args.items or []
        if len(items) > MAX_BULK_ITEMS:
            builder.add_error(
                "INVALID_PARAMS",
                f"bulk memory CRUD limit exceeded (max {MAX_BULK_ITEMS})",
            )
            return builder.build()
        if not items:
            builder.add_error(
                "INVALID_PARAMS",
                "promote requires items with entry_id and target_scope.",
            )
            return builder.build()
        for item in items:
            entry_id = _item_str(item, "entry_id")
            try:
                target_scope = _parse_scope(item.get("target_scope"))
                source_scope = _parse_scope(item.get("source_scope") or args.scope)
            except ValueError as exc:
                builder.add_error("INVALID_PARAMS", str(exc))
                continue
            if not entry_id or target_scope is None:
                builder.add_error(
                    "INVALID_PARAMS",
                    "entry_id and target_scope are required for promote.",
                )
                continue
            try:
                promoted = self._service.promote_entry(
                    actor=self._actor_context,
                    entry_id=entry_id,
                    source_scope=source_scope,
                    target_scope=target_scope,
                    namespace=args.namespace,
                    target_team_id=_item_int(item, "target_team_id"),
                )
                builder.items.append(_entry_to_payload(promoted))
            except PermissionError as exc:
                builder.add_error("FORBIDDEN", str(exc))
            except ValueError as exc:
                message = str(exc)
                code = "NOT_FOUND" if "not found" in message else "INVALID_PARAMS"
                builder.add_error(code, message)
        return builder.build()


def _build_memory_service() -> MemoryCrudService:
    config = load_memory_backend_config()
    registry = build_memory_registry(config)
    return MemoryCrudService(
        registry=registry,
        metrics=build_memory_metrics(),
        audit_sink=LoggingMemoryAuditSink(),
    )


def _build_actor_context(agent_id: AgentId) -> MemoryActorContext:
    system = get_system_from_agent_id(agent_id.__str__())
    if system is None:
        raise ValueError(f"System record not found for agent id {agent_id}.")
    system_type = system.type
    if not isinstance(system_type, SystemType):
        raise ValueError("System type is invalid for memory CRUD context.")
    return MemoryActorContext(
        agent_id=agent_id.__str__(),
        system_id=system.id,
        team_id=system.team_id,
        system_type=system_type,
    )


def _parse_scope(value: Any) -> MemoryScope | None:
    if value is None:
        return None
    try:
        return MemoryScope(str(value))
    except ValueError as exc:
        raise ValueError(f"Invalid scope '{value}'.") from exc


def _parse_layer(value: Any) -> MemoryLayer | None:
    if value is None:
        return None
    try:
        return MemoryLayer(str(value))
    except ValueError as exc:
        raise ValueError(f"Invalid layer '{value}'.") from exc


def _parse_priority(value: Any) -> MemoryPriority | None:
    if value is None:
        return None
    try:
        return MemoryPriority(str(value))
    except ValueError as exc:
        raise ValueError(f"Invalid priority '{value}'.") from exc


def _parse_source(value: Any) -> MemorySource | None:
    if value is None:
        return None
    try:
        return MemorySource(str(value))
    except ValueError as exc:
        raise ValueError(f"Invalid source '{value}'.") from exc


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise ValueError("expires_at must be ISO-8601 datetime string.")


def _entry_to_payload(entry: MemoryEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "scope": entry.scope.value,
        "namespace": entry.namespace,
        "owner_agent_id": entry.owner_agent_id,
        "content": entry.content,
        "tags": list(entry.tags),
        "priority": entry.priority.value,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
        "source": entry.source.value,
        "confidence": entry.confidence,
        "layer": entry.layer.value,
        "version": entry.version,
        "etag": entry.etag,
        "conflict": entry.conflict,
        "conflict_of": entry.conflict_of,
    }


def _build_create_request(
    namespace: str | None,
    scope: MemoryScope | None,
    item: dict[str, Any],
) -> MemoryCreateRequest | MemoryCrudError:
    content = _item_str(item, "content")
    priority = _parse_priority(item.get("priority"))
    source = _parse_source(item.get("source"))
    confidence = _item_float(item, "confidence")
    if not content:
        return MemoryCrudError(code="INVALID_PARAMS", message="content is required.")
    if priority is None:
        return MemoryCrudError(code="INVALID_PARAMS", message="priority is required.")
    if source is None:
        return MemoryCrudError(code="INVALID_PARAMS", message="source is required.")
    if confidence is None:
        return MemoryCrudError(code="INVALID_PARAMS", message="confidence is required.")
    return MemoryCreateRequest(
        content=content,
        namespace=namespace,
        scope=scope,
        tags=_item_list(item, "tags"),
        priority=priority,
        source=source,
        confidence=confidence,
        expires_at=_parse_datetime(item.get("expires_at")),
        layer=_parse_layer(item.get("layer")),
        owner_agent_id=_item_str(item, "owner_agent_id"),
        entry_id=_item_str(item, "entry_id"),
        target_team_id=_item_int(item, "target_team_id"),
    )


def _item_str(item: dict[str, Any], key: str) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    return str(value)


def _item_int(item: dict[str, Any], key: str) -> int | None:
    value = item.get(key)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return int(str(value))


def _item_float(item: dict[str, Any], key: str) -> float | None:
    value = item.get(key)
    if value is None:
        return None
    if isinstance(value, float):
        return value
    return float(str(value))


def _item_list(item: dict[str, Any], key: str) -> list[str] | None:
    value = item.get(key)
    if value is None:
        return None
    if isinstance(value, list):
        return [str(value_item) for value_item in value]
    raise ValueError(f"{key} must be a list.")
