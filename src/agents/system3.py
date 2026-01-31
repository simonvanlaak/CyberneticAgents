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
from src.enums import PolicyJudgement, Status
from src.models import policy
from src.models.system import get_system
from src.models.task import Task, get_task


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

    @message_handler
    async def handle_initiative_assign_message(
        self, message: InitiativeAssignMessage, ctx: MessageContext
    ) -> None:
        # Fetch initiative from database using initiative_id
        from src.models.initiative import get_initiative

        initiative = get_initiative(message.initiative_id)
        if not initiative:
            raise ValueError(f"Initiative with id {message.initiative_id} not found")

        initiative.set_status(Status.IN_PROGRESS)
        initiative.update()

        message_specific_prompts = [
            "## INITIATIVE ASSIGNMENT",
            "You have received an initiative assignment. Your task is to:",
            "1. Review the initiative and ensure you understand the objectives, and how they fit into the overall strategy.",
            "2. Project Planning: Turn an abstract initiative into distinct tasks.",
            "3. Assign Tasks: Assign tasks to the System 1 agents with the required capabilities.",
            "### INITIATIVE",
            json.dumps(initiative.__dict__, indent=4),
            "## AVAILABLE SYSTEM 1s",
            json.dumps(self._get_systems_by_type(1).__dict__, indent=4),
        ]
        break_down_tasks_assignment = message_specific_prompts
        break_down_tasks_assignment.extend(
            [
                "## ASSIGNMENT",
                "Start now with breaking down the initiative into tasks.",
                "Don't set the id, assignee, status, or result.",
            ]
        )

        # Phase 1: Use structured output to create tasks (NO tools available)
        # Remove tools temporarily to avoid conflicts with structured output
        original_tools = self.tools.copy()
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
            task = Task(
                team_id=self.team_id,
                initiative_id=message.initiative_id,
                name=task_response.name,
                content=task_response.content,
            )
            task.add()
            tasks.append(task)

        assign_tasks_assignment = message_specific_prompts
        assign_tasks_assignment.extend(
            [
                "## TASKS",
                *[task.to_prompt() for task in tasks],
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
        task = get_task(message.task_id)
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
        task = get_task(message.task_id)
        if not task.assignee:
            raise ValueError("Task has no assignee")
        policy_chunk = policy.get_system_policy_prompts(task.assignee)
        system_5_id = self._get_systems_by_type(type=5)[0].get_agent_id()
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
                    task.set_status(Status.APPROVED)
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
        assignee = get_system(system_id)
        task = get_task(task_id)
        task.assignee = assignee.agent_id_str
        task.update()
        await self._publish_message_to_agent(
            TaskAssignMessage(
                task_id=task_id,
                assignee_agent_id_str=assignee,
                source=self.name,
                content=task.name,
            ),
            assignee.get_agent_id(),
        )
