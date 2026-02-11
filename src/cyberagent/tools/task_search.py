"""Tool for searching team tasks and prior task results."""

from __future__ import annotations

from autogen_core import AgentId, CancellationToken
from autogen_core.tools import BaseTool
from pydantic import BaseModel, field_validator
from sqlalchemy import or_

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.system import get_system_from_agent_id
from src.cyberagent.db.models.task import Task
from src.cyberagent.services import systems as systems_service
from src.enums import Status

SKILL_NAME = "task_search"
DEFAULT_LIMIT = 5
MAX_LIMIT = 25


class TaskSearchArgs(BaseModel):
    query: str | None = None
    statuses: list[str] | None = None
    limit: int = DEFAULT_LIMIT
    include_without_result: bool = False

    @field_validator("limit")
    @classmethod
    def _validate_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("limit must be at least 1")
        if value > MAX_LIMIT:
            raise ValueError(f"limit must be <= {MAX_LIMIT}")
        return value


class TaskSearchError(BaseModel):
    code: str
    message: str
    details: dict[str, str] | None = None


class TaskSearchItem(BaseModel):
    task_id: int
    team_id: int
    initiative_id: int | None
    name: str
    content: str
    status: str
    assignee: str | None
    result: str | None
    reasoning: str | None


class TaskSearchResponse(BaseModel):
    items: list[TaskSearchItem]
    errors: list[TaskSearchError]


class TaskSearchTool(BaseTool):
    """Search completed and in-progress tasks within the agent's team."""

    def __init__(self, agent_id: AgentId) -> None:
        self._agent_id = agent_id
        super().__init__(
            name=SKILL_NAME,
            description=(
                "Search tasks in your team by name/content/result to reuse prior work. "
                "Use this before marking a task blocked due to missing context."
            ),
            return_type=TaskSearchResponse,
            args_type=TaskSearchArgs,
        )

    async def run(
        self, args: TaskSearchArgs, cancellation_token: CancellationToken
    ) -> TaskSearchResponse:
        del cancellation_token
        system = get_system_from_agent_id(self._agent_id.__str__())
        if system is None:
            return TaskSearchResponse(
                items=[],
                errors=[
                    TaskSearchError(
                        code="INVALID_STATE",
                        message=f"System record not found for '{self._agent_id}'.",
                    )
                ],
            )
        allowed, deny_category = systems_service.can_execute_skill(
            system.id, SKILL_NAME
        )
        if not allowed:
            details = {"failed_rule_category": deny_category} if deny_category else None
            return TaskSearchResponse(
                items=[],
                errors=[
                    TaskSearchError(
                        code="FORBIDDEN",
                        message=f"Skill '{SKILL_NAME}' is not permitted.",
                        details=details,
                    )
                ],
            )

        resolved_statuses, status_error = _parse_statuses(args.statuses)
        if status_error is not None:
            return TaskSearchResponse(
                items=[],
                errors=[
                    TaskSearchError(code="INVALID_PARAMS", message=status_error),
                ],
            )

        session = next(get_db())
        try:
            query = session.query(Task).filter(Task.team_id == system.team_id)
            if not args.include_without_result:
                query = query.filter(Task.result.isnot(None))
            if resolved_statuses:
                query = query.filter(Task.status.in_(resolved_statuses))
            text_query = (args.query or "").strip()
            if text_query:
                pattern = f"%{text_query}%"
                query = query.filter(
                    or_(
                        Task.name.ilike(pattern),
                        Task.content.ilike(pattern),
                        Task.result.ilike(pattern),
                        Task.reasoning.ilike(pattern),
                    )
                )
            rows = query.order_by(Task.id.desc()).limit(args.limit).all()
        finally:
            session.close()

        return TaskSearchResponse(
            items=[
                TaskSearchItem(
                    task_id=row.id,
                    team_id=row.team_id,
                    initiative_id=row.initiative_id,
                    name=row.name,
                    content=row.content,
                    status=_status_to_text(row.status),
                    assignee=row.assignee,
                    result=row.result,
                    reasoning=row.reasoning,
                )
                for row in rows
            ],
            errors=[],
        )


def _parse_statuses(statuses: list[str] | None) -> tuple[list[Status], str | None]:
    if not statuses:
        return [], None
    resolved: list[Status] = []
    for raw_status in statuses:
        normalized = str(raw_status).strip().lower()
        for status in Status:
            if status.value == normalized or status.name.lower() == normalized:
                resolved.append(status)
                break
        else:
            return [], f"Unknown task status '{raw_status}'."
    return resolved, None


def _status_to_text(raw_status: object) -> str:
    if isinstance(raw_status, Status):
        return raw_status.value
    return str(raw_status)
