import json
import logging
from datetime import datetime, timezone
from typing import Any, List, cast

from autogen_core import AgentId, MessageContext, message_handler
from autogen_core.tools import FunctionTool
from pydantic import BaseModel, ConfigDict

from src.cyberagent.agents.messages import (
    BlockedRemediationContract,
    CapabilityGapMessage,
    InitiativeAssignMessage,
    InitiativeReviewMessage,
    InvalidReviewRecoveryContract,
    PolicySuggestionMessage,
    PolicyVagueMessage,
    PolicyViolationMessage,
    RejectedReplacementContract,
    ResearchRequestMessage,
    TaskAssignMessage,
    TaskReviewMessage,
)
from src.cyberagent.agents.system_base import InternalErrorRoutedError, SystemBase
from src.cyberagent.agents.system3_initiative import (
    handle_initiative_assign_message,
)
from src.cyberagent.services import initiatives as initiative_service
from src.cyberagent.services import procedures as procedures_service
from src.cyberagent.services import policies as policy_service
from src.cyberagent.services import systems as system_service
from src.cyberagent.services import tasks as task_service
from src.cyberagent.db.models.system import get_system_from_agent_id
from src.enums import PolicyJudgement, Status, SystemType

logger = logging.getLogger(__name__)


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


class PendingTaskSelectionResponse(BaseModel):
    task_id: int


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
        self.tools.append(
            FunctionTool(
                self.capability_gap_tool,
                "Escalate a capability gap to System5 when no viable System1 can execute a task.",
            )
        )
        self.tools.append(
            FunctionTool(
                self.request_research_tool,
                "Request System4 research to resolve a blocked task.",
            )
        )
        self.tools.append(
            FunctionTool(
                self.escalate_blocked_task_tool,
                "Escalate blocked-task resolution guidance to System5.",
            )
        )
        self.tools.append(
            FunctionTool(
                self.modify_task_tool,
                "Update task content/reasoning and optionally restart blocked execution.",
            )
        )
        self.tools.append(
            FunctionTool(
                self.cancel_task_tool,
                "Cancel a blocked task when no viable remediation path exists.",
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

    def _is_blocked_task(self, task: object) -> bool:
        raw_status = getattr(task, "status", None)
        status_value = getattr(raw_status, "value", raw_status)
        status_text = str(status_value).strip().lower()
        return "blocked" in status_text

    def _select_retry_operation_system_id(self) -> int:
        operation_systems = self._get_systems_by_type(SystemType.OPERATION)
        if not operation_systems:
            raise ValueError("No operation system found for invalid-review retry.")
        ordered_systems = sorted(
            operation_systems,
            key=lambda system: int(getattr(system, "id")),
        )
        return int(getattr(ordered_systems[0], "id"))

    async def _handle_invalid_review_status(
        self,
        message: TaskReviewMessage,
        task: object,
    ) -> None:
        raw_status = getattr(task, "status", None)
        status_text = getattr(raw_status, "value", raw_status)
        error_summary = (
            "TaskReviewMessage received for non-review-eligible status "
            f"'{status_text}'."
        )
        retry_count, should_auto_retry = task_service.record_invalid_review_event(
            cast(Any, task),
            error_summary,
        )
        await self._route_internal_error_to_policy_system(
            failed_message_type=message.__class__.__name__,
            error_summary=error_summary,
            task_id=getattr(task, "id", None),
            contract=InvalidReviewRecoveryContract(
                task_id=int(getattr(task, "id")),
                initiative_id=(
                    int(getattr(task, "initiative_id"))
                    if isinstance(getattr(task, "initiative_id", None), int)
                    else None
                ),
                observed_status=str(status_text),
                retry_count=retry_count,
                retry_limit=task_service.INVALID_REVIEW_AUTO_RETRY_LIMIT,
                error_summary=error_summary,
                next_action=(
                    "auto_retry_assignment"
                    if should_auto_retry
                    else "wait_for_policy_remediation"
                ),
            ),
        )
        if not should_auto_retry:
            logger.info(
                "Invalid-review retry cap reached for task_id=%s (retry_count=%s). Waiting for System5 remediation.",
                getattr(task, "id", None),
                retry_count,
            )
            return

        selected_system_id = self._select_retry_operation_system_id()
        logger.info(
            "Retrying invalid-review task_id=%s via system_id=%s (retry_count=%s).",
            getattr(task, "id", None),
            selected_system_id,
            retry_count,
        )
        await self.assign_task(selected_system_id, int(getattr(task, "id")))

    async def _resolve_blocked_task(
        self,
        message: TaskReviewMessage,
        ctx: MessageContext,
        task: object,
    ) -> None:
        blocked_context = {
            "task_id": getattr(task, "id", None),
            "task_name": getattr(task, "name", ""),
            "task_content": getattr(task, "content", ""),
            "task_reasoning": getattr(task, "reasoning", ""),
            "task_result": getattr(task, "result", ""),
            "task_assignee": getattr(task, "assignee", ""),
            "review_message_content": message.content,
        }
        message_specific_prompts = [
            "Task is currently blocked and needs proactive resolution before policy review.",
            "## BLOCKED TASK CONTEXT",
            json.dumps(blocked_context, indent=4),
            "Analyze why this task is blocked and resolve it now.",
            "You must call exactly one of these tools:",
            f"- {self.request_research_tool.__name__}: when more external/user information is needed.",
            f"- {self.escalate_blocked_task_tool.__name__}: when policy/capability guidance from System5 is needed.",
            f"- {self.modify_task_tool.__name__}: when task wording/reasoning should be adjusted and execution should restart.",
            f"- {self.cancel_task_tool.__name__}: when remediation is not viable and this task attempt must end as canceled.",
            "Do not perform policy judgement in this step.",
        ]
        response = await self.run(
            [message],
            ctx,
            message_specific_prompts,
            include_memory_context=False,
        )
        if not (
            self._was_tool_called(response, self.request_research_tool.__name__)
            or self._was_tool_called(response, self.escalate_blocked_task_tool.__name__)
            or self._was_tool_called(response, self.modify_task_tool.__name__)
            or self._was_tool_called(response, self.cancel_task_tool.__name__)
        ):
            raise ValueError("No blocked-task resolution tool was called.")

    def _task_status_text(self, task: object) -> str:
        raw_status = getattr(task, "status", None)
        status_value = getattr(raw_status, "value", raw_status)
        return str(status_value).strip().lower()

    def _initiative_status_text(self, initiative: object) -> str:
        raw_status = getattr(initiative, "status", None)
        status_value = getattr(raw_status, "value", raw_status)
        return str(status_value).strip().lower()

    def _is_terminal_task_status(self, task: object) -> bool:
        return self._task_status_text(task) in {
            "approved",
            "status.approved",
            "canceled",
            "status.canceled",
        }

    async def _select_pending_task_for_progression(
        self,
        *,
        pending_tasks: list[object],
        message: object,
        ctx: MessageContext,
    ) -> object:
        if len(pending_tasks) == 1:
            return pending_tasks[0]

        pending_payload = [
            {
                "task_id": getattr(task, "id", None),
                "name": getattr(task, "name", ""),
                "content": getattr(task, "content", ""),
                "reasoning": getattr(task, "reasoning", ""),
                "assignee": getattr(task, "assignee", None),
            }
            for task in pending_tasks
        ]
        prompts = [
            "Select the single most important pending task to execute next.",
            'Return strict JSON only with schema: {"task_id": <int>}.',
            "Use business impact and urgency to prioritize.",
            "## Pending Tasks",
            json.dumps(pending_payload, indent=4),
        ]

        try:
            response = await self.run(
                [cast(Any, message)],
                ctx,
                prompts,
                PendingTaskSelectionResponse,
                include_memory_context=False,
            )
            selection = self._get_structured_message(
                response, PendingTaskSelectionResponse
            )
            selected_task_id = int(selection.task_id)
            for task in pending_tasks:
                task_id = getattr(task, "id", None)
                if isinstance(task_id, int) and task_id == selected_task_id:
                    return task
        except Exception as exc:
            logger.warning(
                "Pending-task selection failed for initiative progression: %s",
                exc,
            )

        valid_tasks = [
            task for task in pending_tasks if isinstance(getattr(task, "id", None), int)
        ]
        if not valid_tasks:
            return pending_tasks[0]
        return min(valid_tasks, key=lambda task: int(getattr(task, "id")))

    async def _publish_initiative_review_once(
        self,
        *,
        initiative: object,
    ) -> None:
        if self._initiative_status_text(initiative) in {
            "completed",
            "status.completed",
        }:
            return

        intelligence_systems = self._get_systems_by_type(SystemType.INTELLIGENCE)
        if not intelligence_systems:
            raise ValueError("No intelligence system found for initiative review.")

        initiative_service.set_initiative_status(
            cast(Any, initiative),
            Status.COMPLETED,
        )
        await self._publish_message_to_agent(
            InitiativeReviewMessage(
                initiative_id=int(getattr(initiative, "id")),
                source=self.name,
                content="All initiative tasks are terminal or no tasks were created.",
            ),
            intelligence_systems[0].get_agent_id(),
        )

    async def _evaluate_initiative_progression(
        self,
        *,
        triggering_task: object,
        message: object,
        ctx: MessageContext,
    ) -> None:
        initiative_id = getattr(triggering_task, "initiative_id", None)
        if not isinstance(initiative_id, int):
            return

        initiative = initiative_service.get_initiative_by_id(initiative_id)
        initiative_tasks = list(initiative.get_tasks())

        if not initiative_tasks:
            await self._publish_initiative_review_once(initiative=initiative)
            return

        pending_tasks = [
            task
            for task in initiative_tasks
            if self._task_status_text(task) in {"pending", "status.pending"}
        ]
        if pending_tasks:
            next_task = await self._select_pending_task_for_progression(
                pending_tasks=pending_tasks,
                message=message,
                ctx=ctx,
            )
            assignee = getattr(next_task, "assignee", None)
            if isinstance(assignee, str) and assignee:
                await self._publish_message_to_agent(
                    TaskAssignMessage(
                        task_id=int(getattr(next_task, "id")),
                        assignee_agent_id_str=assignee,
                        source=self.name,
                        content=str(getattr(next_task, "name", "")),
                    ),
                    AgentId.from_str(assignee),
                )
                return

            await self.assign_task(
                self._select_retry_operation_system_id(),
                int(getattr(next_task, "id")),
            )
            return

        non_terminal_tasks = [
            task for task in initiative_tasks if not self._is_terminal_task_status(task)
        ]
        if non_terminal_tasks:
            return

        await self._publish_initiative_review_once(initiative=initiative)

    @message_handler
    async def handle_initiative_assign_message(
        self, message: InitiativeAssignMessage, ctx: MessageContext
    ) -> None:
        await handle_initiative_assign_message(
            self,
            message,
            ctx,
            tasks_create_response_type=TasksCreateResponse,
            tasks_assign_response_type=TasksAssignResponse,
        )

    @message_handler
    async def handle_capability_gap_message(
        self, message: CapabilityGapMessage, ctx: MessageContext
    ) -> None:
        task = task_service.get_task_by_id(message.task_id)
        if task.assignee is None:
            raise ValueError("Task assignee cannot be None")

        capability_gap_context = {
            "task_id": message.task_id,
            "task_name": getattr(task, "name", ""),
            "task_content": getattr(task, "content", ""),
            "assignee": task.assignee,
            "gap_summary": message.content,
        }
        message_specific_prompts = [
            "You have received a capability gap message.",
            "A System 1 has failed to complete a task, because it is lacking specific capabilities.",
            "## CAPABILITY GAP CONTEXT",
            json.dumps(capability_gap_context, indent=4),
            "You need to identify an alternative System 1 that can handle the task.",
            f"If you successfully identify an alternative System 1, assign it the task using the {self.assign_task.__name__} tool.",
            f"If you fail to identify an alternative System 1, you must escalate the capability gap to System 5 using the {self.capability_gap_tool.__name__} tool.",
            f"You must call either the {self.assign_task.__name__} or the {self.capability_gap_tool.__name__} tool.",
            f"The affected task_id is {message.task_id}. Any tool call must use this exact task_id; never use 0 or placeholders.",
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
        if not task_service.is_review_eligible_for_task(task):
            await self._handle_invalid_review_status(message, task)
            return

        if self._is_blocked_task(task):
            try:
                await self._resolve_blocked_task(message, ctx, task)
                await self._evaluate_initiative_progression(
                    triggering_task=task,
                    message=message,
                    ctx=ctx,
                )
            except Exception as exc:
                if isinstance(exc, InternalErrorRoutedError):
                    return
                await self._route_internal_error_to_policy_system(
                    failed_message_type=message.__class__.__name__,
                    error_summary=str(exc),
                    task_id=getattr(task, "id", None),
                )
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
            await self._evaluate_initiative_progression(
                triggering_task=task,
                message=message,
                ctx=ctx,
            )
            return
        policy_chunks = [
            policy_chunk[i : i + 5] for i in range(0, len(policy_chunk), 5)
        ]
        task_review_context = {
            "task_id": task.id,
            "task_name": getattr(task, "name", ""),
            "task_description": getattr(task, "content", ""),
            "task_result": getattr(task, "result", ""),
            "review_message_content": message.content,
            "task_status": str(getattr(task, "status", "")),
            "task_assignee": task.assignee,
        }
        all_cases: list[dict[str, object]] = []
        try:
            for policy_chunk in policy_chunks:
                message_specific_prompts = [
                    f"Review task result {task.id} for if it violates any policy.",
                    "## Task Review Context",
                    json.dumps(task_review_context, indent=4),
                    "Use task_result as the primary evidence.",
                    "If task_result is missing, use review_message_content.",
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
                                contract=RejectedReplacementContract(
                                    task_id=task.id,
                                    initiative_id=(
                                        int(getattr(task, "initiative_id"))
                                        if isinstance(
                                            getattr(task, "initiative_id", None), int
                                        )
                                        else None
                                    ),
                                    assignee_agent_id_str=task.assignee,
                                    policy_id=case.policy_id,
                                    policy_reasoning=case.reasoning,
                                    case_judgement=getattr(
                                        task, "case_judgement", None
                                    ),
                                    execution_log=getattr(task, "execution_log", None),
                                    requested_outcome=(
                                        "create_replacement_or_remediate"
                                    ),
                                ),
                                source=self.name,
                            ),
                            system_5_id,
                        )
                        # response of system 5 will be handled in a different message handler
                    elif case.judgement == PolicyJudgement.SATISFIED:
                        continue
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
            task_service.finalize_task_review(task, all_cases)
            await self._evaluate_initiative_progression(
                triggering_task=task,
                message=message,
                ctx=ctx,
            )
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

    async def request_research_tool(self, task_id: int, content: str) -> bool:
        task = task_service.get_task_by_id(task_id)
        intelligence_systems = self._get_systems_by_type(SystemType.INTELLIGENCE)
        if not intelligence_systems:
            raise ValueError("No intelligence system found for blocked-task research.")
        await self._publish_message_to_agent(
            ResearchRequestMessage(
                source=self.name,
                content=(
                    f"{content}\n\n"
                    f"Task ID: {task.id}\n"
                    f"Task name: {getattr(task, 'name', '')}\n"
                    f"Task content: {getattr(task, 'content', '')}\n"
                    f"Blocked reasoning: {getattr(task, 'reasoning', '')}"
                ),
            ),
            intelligence_systems[0].get_agent_id(),
        )
        return True

    async def escalate_blocked_task_tool(self, task_id: int, content: str) -> bool:
        task = task_service.get_task_by_id(task_id)
        assignee = getattr(task, "assignee", None)
        if not isinstance(assignee, str) or not assignee:
            raise ValueError(
                "Blocked-task escalation requires a valid task assignee for remediation."
            )

        policy_systems = self._get_systems_by_type(SystemType.POLICY)
        if not policy_systems:
            raise ValueError("No policy system found for blocked-task escalation.")
        await self._publish_message_to_agent(
            CapabilityGapMessage(
                task_id=task_id,
                content=content,
                assignee_agent_id_str=assignee,
                contract=BlockedRemediationContract(
                    task_id=task_id,
                    initiative_id=(
                        int(getattr(task, "initiative_id"))
                        if isinstance(getattr(task, "initiative_id", None), int)
                        else None
                    ),
                    assignee_agent_id_str=assignee,
                    blocked_reasoning=str(getattr(task, "reasoning", "")),
                    remediation_request=content,
                ),
                source=self.name,
            ),
            policy_systems[0].get_agent_id(),
        )
        return True

    async def cancel_task_tool(self, task_id: int, reasoning: str) -> dict[str, object]:
        task = task_service.get_task_by_id(task_id)
        if not self._is_blocked_task(task):
            raise ValueError("Only blocked tasks can be canceled via cancel_task_tool.")

        task.reasoning = reasoning
        task.set_status(Status.CANCELED)
        task_service.persist_task(task)

        return {
            "task_id": task_id,
            "status": str(getattr(task, "status", "")),
            "reasoning": reasoning,
            "replacement_created": False,
        }

    async def modify_task_tool(
        self,
        task_id: int,
        content: str | None = None,
        reasoning: str | None = None,
        restart_execution: bool = False,
    ) -> dict[str, object]:
        task = task_service.get_task_by_id(task_id)

        if restart_execution:
            task = task_service.start_task(task_id)

        if content is not None:
            task.content = content
        if reasoning is not None:
            task.reasoning = reasoning
        task_service.persist_task(task)

        if restart_execution:
            assignee = getattr(task, "assignee", None)
            if not isinstance(assignee, str) or not assignee:
                raise ValueError(
                    "Cannot restart task execution without a valid assignee."
                )
            await self._publish_message_to_agent(
                TaskAssignMessage(
                    task_id=task_id,
                    assignee_agent_id_str=assignee,
                    source=self.name,
                    content=task.name,
                ),
                AgentId.from_str(assignee),
            )
        return {
            "task_id": task_id,
            "status": str(getattr(task, "status", "")),
            "content_updated": content is not None,
            "reasoning_updated": reasoning is not None,
            "restart_execution": restart_execution,
        }

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
