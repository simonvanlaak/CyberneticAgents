import json
from typing import List, Tuple

from autogen_core import MessageContext, message_handler
from autogen_core.tools import FunctionTool
from pydantic import BaseModel, ConfigDict

from src.agents.messages import (
    CapabilityGapMessage,
    InitiativeAssignMessage,
    PolicyVagueMessage,
    PolicyViolationMessage,
    TaskAssignMessage,
    TaskReviewMessage,
)
from src.agents.system_base import SystemBase
from src.cyberagent.services import initiatives as initiative_service
from src.cyberagent.services import procedures as procedures_service
from src.cyberagent.services import policies as policy_service
from src.cyberagent.services import systems as system_service
from src.cyberagent.services import tasks as task_service
from src.cyberagent.db.models.system import get_system_from_agent_id
from src.enums import PolicyJudgement, SystemType
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


class TasksAssignResponse(BaseModel):
    assignments: List[Tuple[int, int]]


class System3(SystemBase):
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

    @message_handler
    async def handle_initiative_assign_message(
        self, message: InitiativeAssignMessage, ctx: MessageContext
    ) -> None:
        init_db()
        initiative = initiative_service.start_initiative(message.initiative_id)
        existing_tasks = []
        if task_service.has_tasks_for_initiative(message.initiative_id):
            existing_tasks = [
                task
                for task in initiative.get_tasks()
                if getattr(task, "assignee", None) is None
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
                "Respond with a list where for each system id you assign a task id.",
            ]
        )

        # Phase 2: Sequential processing approach
        # Option A: Try tool use first (without structured output constraint)
        decision_response = await self.run([message], ctx, assign_tasks_assignment)

        # Check if the tool was called during the decision phase
        if self._was_tool_called(decision_response, self.assign_task.__name__):
            # Tool was called, assignments are complete
            return
        else:
            # Tool wasn't called, get structured assignments and process manually
            # Phase 3: Get structured assignments (NO tools available)
            self.tools = []  # Remove tools to avoid conflict

            assignment_response = await self.run(
                [message], ctx, assign_tasks_assignment, TasksAssignResponse
            )
            tasks_assign_response: TasksAssignResponse = self._get_structured_message(
                assignment_response, TasksAssignResponse
            )

            # Restore tools for future use
            self.tools = original_tools

            # Process assignments manually since tool wasn't called
            for system_id, task_id in tasks_assign_response.assignments:
                await self.assign_task(system_id, task_id)

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
        policy_chunk = policy_service.get_system_policy_prompts(task.assignee)
        policy_systems = self._get_systems_by_type(SystemType.POLICY)
        if not policy_systems:
            raise ValueError("No policy system found for team.")
        system_5_id = policy_systems[0].get_agent_id()
        # break down policies into chunks of 5
        if len(policy_chunk) == 0:
            # TODO: send a policy suggestion here
            raise ValueError("No policies found")
        policy_chunks = [
            policy_chunk[i : i + 5] for i in range(0, len(policy_chunk), 5)
        ]
        for policy_chunk in policy_chunks:
            message_specific_prompts = [
                f"Review task result {task.id} for if it violates any policy."
                "## Policies",
                *policy_chunk,
                "## Response",
                "You are required to judge each policy as vague, violated, or passed.",
            ]
            response = await self.run(
                [message], ctx, message_specific_prompts, CasesResponse
            )

            cases_response = self._get_structured_message(response, CasesResponse)

            for case in cases_response.cases:
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
                source=str(self.agent_id),
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
