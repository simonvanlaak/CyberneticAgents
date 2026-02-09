import json
from datetime import datetime, timezone
from typing import Any, List, cast

from autogen_core import AgentId, MessageContext, message_handler
from autogen_core.tools import FunctionTool
from pydantic import BaseModel, ConfigDict

from src.agents.messages import (
    CapabilityGapMessage,
    InitiativeAssignMessage,
    PolicySuggestionMessage,
    PolicyVagueMessage,
    PolicyViolationMessage,
    TaskAssignMessage,
    TaskReviewMessage,
)
from src.agents.system_base import InternalErrorRoutedError, SystemBase
from src.cyberagent.services import initiatives as initiative_service
from src.cyberagent.services import procedures as procedures_service
from src.cyberagent.services import policies as policy_service
from src.cyberagent.services import systems as system_service
from src.cyberagent.services import tasks as task_service
from src.cyberagent.db.models.system import get_system_from_agent_id
from src.enums import PolicyJudgement, Status, SystemType
from src.cyberagent.db.init_db import init_db


class PolicyJudgeResponse(BaseModel):
    policy_id: int
    judgement: PolicyJudgement
    reasoning: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


class TaskCreateResponse(BaseModel):
    name: str
    content: str


class TasksCreateResponse(BaseModel):
    tasks: List[TaskCreateResponse]


class CasesResponse(BaseModel):
    cases: List[PolicyJudgeResponse]


class TaskAssignmentResponse(BaseModel):
    system_id: int
    task_id: int


class TasksAssignResponse(BaseModel):
    assignments: List[TaskAssignmentResponse]


class System3(SystemBase):
    REVIEW_PARSE_FAILURE_MAX_RETRIES = 2

    def __init__(self, name: str, trace_context: dict | None = None):
        super().__init__(
            name,
            identity_prompt="""
            You are the operational control agent responsible for monitoring and controlling System 1 operational units.
            You represent the 'big picture' view of operations and ensure System 1 agents operate effectively within organizational policies.
            """,
            responsibility_prompts=[
                "1. Operational Delegation: Assign tasks to System 1 agents.",
                "2. Project Planning: Turn an abstract initiative into distinct tasks.",
                "3. Task Review: Ensure that tasks have been completed successfully, and followed policies.",
            ],
            trace_context=trace_context,
        )
        self.tools.append(
            FunctionTool(
                self.assign_task, "Trigger the execution of a task by a system 1."
            )
        )
        self.tools.append(
            FunctionTool(
                self.execute_procedure_tool,
                "Execute an approved procedure by materializing an initiative and tasks.",
            )
        )

    def _extract_parse_failure_retry_count(self, task: Any) -> int:
        raw_case_judgement = getattr(task, "case_judgement", None)
        if not isinstance(raw_case_judgement, str) or not raw_case_judgement.strip():
            return 0
        try:
            payload = json.loads(raw_case_judgement)
        except json.JSONDecodeError:
            return 0
        if not isinstance(payload, list):
            return 0
        max_retry = 0
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            if entry.get("kind") != "review_parse_failure":
                continue
            retry_raw = entry.get("retry_count")
            if isinstance(retry_raw, int):
                max_retry = max(max_retry, retry_raw)
        return max_retry

    async def _handle_review_parse_failure(
        self,
        *,
        task: Any,
        system_5_id: AgentId,
        phase: str,
        error: Exception,
    ) -> None:
        previous_retry_count = self._extract_parse_failure_retry_count(task)
        retry_count = previous_retry_count + 1
        retry_exhausted = retry_count >= self.REVIEW_PARSE_FAILURE_MAX_RETRIES
        failure_case = [
            {
                "kind": "review_parse_failure",
                "phase": phase,
                "reason": str(error),
                "retry_count": retry_count,
                "retry_exhausted": retry_exhausted,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
        task_service.set_task_case_judgement(cast(Any, task), failure_case)
        task_id = int(getattr(task, "id"))
        retry_fragment = (
            "Max retries reached; manual intervention required."
            if retry_exhausted
            else "Requesting review retry."
        )
        await self._publish_message_to_agent(
            PolicySuggestionMessage(
                policy_id=None,
                task_id=task_id,
                content=(
                    "Task review parse failure for "
                    f"task {task_id} (phase={phase}, retry {retry_count}/"
                    f"{self.REVIEW_PARSE_FAILURE_MAX_RETRIES}). "
                    f"{retry_fragment}"
                ),
                source=self.name,
            ),
            system_5_id,
        )

    @message_handler
    async def handle_initiative_assign_message(
        self, message: InitiativeAssignMessage, ctx: MessageContext
    ) -> None:
        init_db()
        initiative = initiative_service.start_initiative(message.initiative_id)
        existing_tasks = []
        if task_service.has_tasks_for_initiative(message.initiative_id):
            all_tasks = list(initiative.get_tasks())

            def _task_status_value(task: object) -> str:
                raw_status = getattr(task, "status", None)
                status_value = getattr(raw_status, "value", raw_status)
                return str(status_value).lower()

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
        from typing import Any

        systems: Any = self._get_systems_by_type(SystemType.OPERATION)
        systems_list = systems.systems if hasattr(systems, "systems") else systems
        systems_payload = [
            {
                "id": system.id,
                "name": system.name,
                "type": (
                    system.type.value
                    if hasattr(system.type, "value")
                    else str(system.type)
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
            # Phase 1: Use structured output to create tasks (NO tools available)
            # Remove tools temporarily to avoid conflicts with structured output
            self.tools = []  # Remove tools to avoid conflict with structured output

            response = await self.run(
                [message], ctx, break_down_tasks_assignment, TasksCreateResponse
            )

            # Restore tools for potential future use
            self.tools = original_tools

            tasks_create_response: TasksCreateResponse = self._get_structured_message(
                response, TasksCreateResponse
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

        assign_tasks_assignment = message_specific_prompts
        task_prompt_lines = [line for task in tasks for line in task.to_prompt()]
        assign_tasks_assignment.extend(
            [
                "## TASKS",
                *task_prompt_lines,
                "## ASSIGNMENT",
                "After having created the tasks, assign the one that needs to be completed first to a System 1 agent.",
                "Return strict JSON only using this schema:",
                '{"assignments":[{"system_id":1,"task_id":7}]}',
                "Rules:",
                "1. assignments must be a list of objects with integer system_id and integer task_id.",
                "2. Do not return arrays/tuples like [1,7].",
                "3. Do not add prose, markdown, or explanation.",
                "4. Assign exactly one next task for now.",
            ]
        )

        # Phase 2: Structured assignment output only (NO tools available)
        self.tools = []  # Remove tools to avoid conflict

        assignment_response = await self.run(
            [message], ctx, assign_tasks_assignment, TasksAssignResponse
        )
        tasks_assign_response: TasksAssignResponse = self._get_structured_message(
            assignment_response, TasksAssignResponse
        )

        # Restore tools for future use
        self.tools = original_tools

        # Process assignments from structured output
        for assignment in tasks_assign_response.assignments:
            await self.assign_task(assignment.system_id, assignment.task_id)

    @message_handler
    async def handle_capability_gap_message(
        self, message: CapabilityGapMessage, ctx: MessageContext
    ) -> None:
        task = task_service.get_task_by_id(message.task_id)
        if task.assignee is None:
            raise ValueError("Task assignee cannot be None")

        message_specific_prompts = [
            "You have received a capability gap message.",
            "A System 1 has failed to complete a task, because it is lacking specific capabilities.",
            "You need to identify an alternative System 1 that can handle the task.",
            f"If you successfully identify an alternative System 1, assign it the task using the {self.assign_task.__name__} tool.",
            f"If you fail to identify an alternative System 1, you must escalate the capability gap to System 5 using the {self.capability_gap_tool.__name__} tool.",
            f"You must call either the {self.assign_task.__name__} or the {self.capability_gap_tool.__name__} tool.",
        ]
        response = await self.run([message], ctx, message_specific_prompts)
        if not (
            self._was_tool_called(response, self.assign_task.__name__)
            or self._was_tool_called(response, self.capability_gap_tool.__name__)
        ):
            raise ValueError("No tool was called")

    @message_handler
    async def handle_task_review_message(
        self, message: TaskReviewMessage, ctx: MessageContext
    ) -> None:
        task = task_service.get_task_by_id(message.task_id)
        if not task.assignee:
            raise ValueError("Task has no assignee")
        task_status = getattr(task, "status", None)
        status_value = getattr(task_status, "value", task_status)
        if task_status == Status.BLOCKED or str(status_value).lower() in {
            "blocked",
            "status.blocked",
        }:
            return
        policy_chunk = policy_service.get_system_policy_prompts(task.assignee)
        policy_systems = self._get_systems_by_type(SystemType.POLICY)
        if not policy_systems:
            raise ValueError("No policy system found for team.")
        system_5_id = policy_systems[0].get_agent_id()
        # break down policies into chunks of 5
        if len(policy_chunk) == 0:
            await self._publish_message_to_agent(
                PolicySuggestionMessage(
                    policy_id=None,
                    task_id=task.id,
                    content=(
                        "Task review could not run because no policies exist for "
                        f"assignee '{task.assignee}'. Create baseline review "
                        "policies defining completion criteria, evidence "
                        f"requirements, and safety constraints for task {task.id}."
                    ),
                    source=self.name,
                ),
                system_5_id,
            )
            return
        policy_chunks = [
            policy_chunk[i : i + 5] for i in range(0, len(policy_chunk), 5)
        ]
        all_cases: list[dict[str, object]] = []
        try:
            for policy_chunk in policy_chunks:
                message_specific_prompts = [
                    f"Review task result {task.id} for if it violates any policy."
                    "## Policies",
                    *policy_chunk,
                    "## Response",
                    "You are required to judge each policy as vague, violated, or passed.",
                ]
                try:
                    response = await self.run(
                        [message],
                        ctx,
                        message_specific_prompts,
                        CasesResponse,
                        include_memory_context=False,
                    )
                    cases_response = self._get_structured_message(
                        response, CasesResponse
                    )
                except Exception as exc:
                    if isinstance(exc, ValueError):
                        await self._handle_review_parse_failure(
                            task=task,
                            system_5_id=system_5_id,
                            phase="primary",
                            error=exc,
                        )
                        return
                    if not self._is_json_generation_failure(exc):
                        raise
                    fallback_prompts = [
                        *message_specific_prompts,
                        (
                            "Return strict JSON only with this schema: "
                            '{"cases":[{"policy_id":<int>,"judgement":"Vague|Violated|Satisfied","reasoning":"<string>"}]}'
                        ),
                        "Do not include markdown or prose outside the JSON object.",
                    ]
                    fallback_response = await self.run(
                        [message],
                        ctx,
                        fallback_prompts,
                        None,
                        include_memory_context=False,
                    )
                    try:
                        cases_response = self._get_structured_message(
                            fallback_response, CasesResponse
                        )
                    except ValueError as fallback_exc:
                        await self._handle_review_parse_failure(
                            task=task,
                            system_5_id=system_5_id,
                            phase="fallback",
                            error=fallback_exc,
                        )
                        return

                for case in cases_response.cases:
                    all_cases.append(
                        {
                            "policy_id": case.policy_id,
                            "judgement": case.judgement.value,
                            "reasoning": case.reasoning,
                        }
                    )
                    if case.judgement == PolicyJudgement.VIOLATED:
                        await self._publish_message_to_agent(
                            PolicyViolationMessage(
                                task_id=task.id,
                                assignee_agent_id_str=task.assignee,
                                policy_id=case.policy_id,
                                content=case.reasoning,
                                source=self.name,
                            ),
                            system_5_id,
                        )
                        # response of system 5 will be handled in a different message handler
                    elif case.judgement == PolicyJudgement.SATISFIED:
                        task_service.approve_task(task)
                        # check if system should get another task assigned
                    elif case.judgement == PolicyJudgement.VAGUE:
                        await self._publish_message_to_agent(
                            PolicyVagueMessage(
                                task_id=task.id,
                                policy_id=case.policy_id,
                                content=case.reasoning,
                                source=self.name,
                            ),
                            system_5_id,
                        )
                        # system 5 will call this message handler again once it has clarified the policy.
                    else:
                        raise ValueError("Invalid policy judgement")
            task_service.set_task_case_judgement(task, all_cases)
        except Exception as exc:
            if isinstance(exc, InternalErrorRoutedError):
                return
            await self._route_internal_error_to_policy_system(
                failed_message_type=message.__class__.__name__,
                error_summary=str(exc),
                task_id=task.id,
            )

    async def assign_task(self, system_id: int, task_id: int):
        assignee = system_service.get_system(system_id)
        if assignee is None:
            raise ValueError(f"System {system_id} not found.")
        task = task_service.get_task_by_id(task_id)
        if assignee.agent_id_str is None:
            raise ValueError(f"System {system_id} has no agent id.")
        task_service.assign_task(task, assignee.agent_id_str)
        await self._publish_message_to_agent(
            TaskAssignMessage(
                task_id=task_id,
                assignee_agent_id_str=assignee.agent_id_str,
                source=self.name,
                content=task.name,
            ),
            assignee.get_agent_id(),
        )

    def execute_procedure_tool(
        self, procedure_id: int, strategy_id: int
    ) -> dict[str, object]:
        """
        Execute an approved procedure by creating an initiative and tasks.
        """
        system = get_system_from_agent_id(self.agent_id.__str__())
        if system is None:
            raise ValueError("System record not found for this agent.")
        run = procedures_service.execute_procedure(
            procedure_id=procedure_id,
            team_id=self.team_id,
            strategy_id=strategy_id,
            executed_by_system_id=system.id,
        )
        return {
            "procedure_run_id": run.id,
            "initiative_id": run.initiative_id,
            "status": run.status,
        }
