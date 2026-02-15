from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from autogen_core import AgentId, MessageContext

from src.cyberagent.agents.messages import InitiativeAssignMessage, TaskAssignMessage
from src.cyberagent.services import initiatives as initiative_service
from src.cyberagent.services import tasks as task_service
from src.cyberagent.db.init_db import init_db
from src.enums import SystemType

if TYPE_CHECKING:
    from src.cyberagent.agents.system3 import System3

logger = logging.getLogger(__name__)


async def handle_initiative_assign_message(
    system3: "System3",
    message: InitiativeAssignMessage,
    ctx: MessageContext,
    tasks_create_response_type: type[Any],
    tasks_assign_response_type: type[Any],
) -> None:
    self = system3
    init_db()
    initiative = initiative_service.start_initiative(message.initiative_id)
    existing_tasks: list[Any] = []
    if task_service.has_tasks_for_initiative(message.initiative_id):
        all_tasks = list(initiative.get_tasks())

        def _task_status_value(task: object) -> str:
            raw_status = getattr(task, "status", None)
            status_value = getattr(raw_status, "value", raw_status)
            return str(status_value).lower()

        in_progress_assigned_tasks = [
            task
            for task in all_tasks
            if getattr(task, "assignee", None)
            and _task_status_value(task)
            in {
                "in_progress",
                "status.in_progress",
            }
        ]
        if in_progress_assigned_tasks:
            for in_progress_task in in_progress_assigned_tasks:
                assignee = getattr(in_progress_task, "assignee", None)
                if not isinstance(assignee, str):
                    continue
                await self._publish_message_to_agent(
                    TaskAssignMessage(
                        task_id=in_progress_task.id,
                        assignee_agent_id_str=assignee,
                        source=self.name,
                        content=in_progress_task.name,
                    ),
                    AgentId.from_str(assignee),
                )
            return

        pending_assigned_tasks = [
            task
            for task in all_tasks
            if getattr(task, "assignee", None)
            and _task_status_value(task) in {"pending", "status.pending"}
        ]
        if pending_assigned_tasks:
            pending_task = pending_assigned_tasks[0]
            assignee = getattr(pending_task, "assignee", None)
            if isinstance(assignee, str):
                await self._publish_message_to_agent(
                    TaskAssignMessage(
                        task_id=pending_task.id,
                        assignee_agent_id_str=assignee,
                        source=self.name,
                        content=pending_task.name,
                    ),
                    AgentId.from_str(assignee),
                )
            return

        existing_tasks = [
            task for task in all_tasks if getattr(task, "assignee", None) is None
        ]
        if not existing_tasks:
            return

    initiative_payload = {
        "id": getattr(initiative, "id", None),
        "team_id": getattr(initiative, "team_id", None),
        "strategy_id": getattr(initiative, "strategy_id", None),
        "status": (
            initiative.status.value
            if hasattr(initiative, "status") and hasattr(initiative.status, "value")
            else str(getattr(initiative, "status", ""))
        ),
        "name": getattr(initiative, "name", ""),
        "description": getattr(initiative, "description", ""),
        "result": getattr(initiative, "result", None),
    }
    systems: Any = self._get_systems_by_type(SystemType.OPERATION)
    systems_list = systems.systems if hasattr(systems, "systems") else systems
    systems_payload = [
        {
            "id": system.id,
            "name": system.name,
            "type": (
                system.type.value if hasattr(system.type, "value") else str(system.type)
            ),
            "agent_id_str": system.agent_id_str,
        }
        for system in systems_list
    ]
    message_specific_prompts = [
        "## INITIATIVE ASSIGNMENT",
        "You have received an initiative assignment. Your task is to:",
        "1. Review the initiative and ensure you understand the objectives, and how they fit into the overall strategy.",
        "2. Project Planning: Turn an abstract initiative into distinct tasks.",
        "3. Assign Tasks: Assign tasks to the System 1 agents with the required capabilities.",
        "### INITIATIVE",
        json.dumps(initiative_payload, indent=4),
        "## AVAILABLE SYSTEM 1s",
        json.dumps(systems_payload, indent=4),
    ]
    break_down_tasks_assignment = message_specific_prompts
    break_down_tasks_assignment.extend(
        [
            "## ASSIGNMENT",
            "Start now with breaking down the initiative into tasks.",
            "Don't set the id, assignee, status, or result.",
        ]
    )

    original_tools = self.tools.copy()
    if existing_tasks:
        tasks = existing_tasks
    else:
        self.tools = []

        response = await self.run(
            [message], ctx, break_down_tasks_assignment, tasks_create_response_type
        )

        self.tools = original_tools

        tasks_create_response = self._get_structured_message(
            response, tasks_create_response_type
        )
        tasks = []
        for task_response in tasks_create_response.tasks:
            task = task_service.create_task(
                team_id=self.team_id,
                initiative_id=message.initiative_id,
                name=task_response.name,
                content=task_response.content,
            )
            tasks.append(task)

    if not tasks:
        await self._publish_initiative_review_once(initiative=initiative)
        return

    assign_tasks_assignment = message_specific_prompts
    task_prompt_lines = [line for task in tasks for line in task.to_prompt()]
    example_task_id = 1
    if tasks:
        first_task_id = getattr(tasks[0], "id", None)
        if isinstance(first_task_id, int):
            example_task_id = first_task_id
    assign_tasks_assignment.extend(
        [
            "## TASKS",
            *task_prompt_lines,
            "## ASSIGNMENT",
            "After having created the tasks, assign the one that needs to be completed first to a System 1 agent.",
            "Return strict JSON only using this schema:",
            f'{{"assignments":[{{"system_id":1,"task_id":{example_task_id}}}]}}',
            "Rules:",
            "1. assignments must be a list of objects with integer system_id and integer task_id.",
            "2. Do not return arrays/tuples like [1,7].",
            "3. Do not add prose, markdown, or explanation.",
            "4. Assign exactly one next task for now.",
        ]
    )

    self.tools = []

    assignment_response = await self.run(
        [message], ctx, assign_tasks_assignment, tasks_assign_response_type
    )
    tasks_assign_response = self._get_structured_message(
        assignment_response, tasks_assign_response_type
    )

    self.tools = original_tools

    available_task_ids = {
        int(getattr(task, "id"))
        for task in tasks
        if isinstance(getattr(task, "id", None), int)
    }
    validate_assignment_task_ids = len(available_task_ids) > 0
    assignment_applied = False
    for assignment in tasks_assign_response.assignments:
        if (
            validate_assignment_task_ids
            and assignment.task_id not in available_task_ids
        ):
            logger.warning(
                "Ignoring invalid task assignment candidate task_id=%s for initiative=%s. Available task ids: %s",
                assignment.task_id,
                message.initiative_id,
                sorted(available_task_ids),
            )
            continue
        await self.assign_task(assignment.system_id, assignment.task_id)
        assignment_applied = True

    if assignment_applied:
        return

    if not validate_assignment_task_ids:
        return
    if not available_task_ids:
        return
    if not systems_list:
        logger.warning(
            "No available System1 for fallback assignment on initiative=%s.",
            message.initiative_id,
        )
        await self._publish_initiative_review_once(initiative=initiative)
        return
    fallback_system_id = int(getattr(systems_list[0], "id"))
    fallback_task_id = min(available_task_ids)
    logger.warning(
        "No valid structured assignment returned for initiative=%s. Falling back to system_id=%s task_id=%s.",
        message.initiative_id,
        fallback_system_id,
        fallback_task_id,
    )
    await self.assign_task(fallback_system_id, fallback_task_id)
