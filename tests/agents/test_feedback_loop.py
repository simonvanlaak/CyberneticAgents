import asyncio
import uuid

import pytest
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import StructuredMessage, TextMessage
from autogen_core import AgentId, CancellationToken, MessageContext

from src.agents.messages import StrategyRequestMessage, UserMessage
from src.agents.system1 import System1
from src.agents.system3 import (
    System3,
    TaskCreateResponse,
    TasksAssignResponse,
    TasksCreateResponse,
)
from src.agents.system4 import (
    InitiativeAssignResponse,
    InitiativeCreateResponse,
    StrategyCreateResponse,
    System4,
)
from src.cli_session import (
    clear_pending_questions,
    enqueue_pending_question,
    get_pending_question,
    resolve_pending_question,
    wait_for_answer,
)
from src.cyberagent.db.db_utils import get_db
from src.enums import Status, SystemType
from src.cyberagent.db.init_db import init_db
from src.cyberagent.db.models.initiative import Initiative
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.task import Task
from src.cyberagent.db.models.team import Team

TEST_PROMPT = (
    "I need product discovery research that evaluates how the technology of Multi "
    "Agent Systems could be turned into a product and what potential customers exist "
    "there. I don't have a specific industry in mind yet. I have 1 month time and a "
    "budget of 200 Euros. I have a working technical prototype. Don't ask me more "
    "questions, but start creating & implementing a strategy."
)


def _create_team_with_systems() -> tuple[int, int]:
    team = Team(name=f"feedback_team_{uuid.uuid4().hex}")
    db = next(get_db())
    db.add(team)
    db.commit()
    system1 = System(
        team_id=team.id,
        name="System1 Ops",
        type=SystemType.OPERATION,
        agent_id_str="System1/ops1",
    )
    system3 = System(
        team_id=team.id,
        name="System3 Control",
        type=SystemType.CONTROL,
        agent_id_str="System3/root",
    )
    system4 = System(
        team_id=team.id,
        name="System4 Intelligence",
        type=SystemType.INTELLIGENCE,
        agent_id_str="System4/root",
    )
    db.add_all([system1, system3, system4])
    db.commit()
    team_id = team.id
    system1_id = system1.id
    db.close()
    return team_id, system1_id


@pytest.mark.asyncio
async def test_product_discovery_feedback_loop_creates_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_db()
    clear_pending_questions()
    team_id, system1_id = _create_team_with_systems()

    system4 = System4("System4/root")
    system3 = System3("System3/root")
    system1 = System1("System1/ops1")
    system4._id = system4.agent_id
    system4.team_id = team_id
    system3.team_id = team_id
    system1.team_id = team_id

    async def system4_run(
        chat_messages, ctx, message_specific_prompts=None, output_content_type=None
    ):
        if output_content_type is StrategyCreateResponse:
            response = StrategyCreateResponse(
                name="Product discovery",
                description="Validate product-market fit and early customers.",
                initiatives=[
                    InitiativeCreateResponse(
                        name="Market discovery",
                        description="Identify promising segments and pains.",
                    )
                ],
            )
            return TaskResult(
                messages=[StructuredMessage(content=response, source=system4.name)]
            )
        if output_content_type is InitiativeAssignResponse:
            db = next(get_db())
            initiative = (
                db.query(Initiative)
                .filter(Initiative.team_id == team_id)
                .order_by(Initiative.id.desc())
                .first()
            )
            db.close()
            if initiative is None:
                raise ValueError("No initiative found for assignment.")
            initiative_id = initiative.id
            return TaskResult(
                messages=[
                    StructuredMessage(
                        content=InitiativeAssignResponse(initiative_id=initiative_id),
                        source=system4.name,
                    )
                ]
            )

        loop = asyncio.get_running_loop()
        question_id = enqueue_pending_question(
            "What outcome matters most in the first month?",
            asked_by="System4",
            loop=loop,
        )
        await wait_for_answer(question_id, timeout_seconds=2)
        question_id = enqueue_pending_question(
            "Who is the first customer persona to target?",
            asked_by="System4",
            loop=loop,
        )
        await wait_for_answer(question_id, timeout_seconds=2)
        await system4.handle_strategy_request_message(
            message=StrategyRequestMessage(
                content=chat_messages[-1].content, source="System4/root"
            ),
            ctx=ctx,
        )  # type: ignore[call-arg]
        return TaskResult(
            messages=[TextMessage(content="User input captured.", source=system4.name)]
        )

    async def system3_run(
        chat_messages, ctx, message_specific_prompts=None, output_content_type=None
    ):
        if output_content_type is TasksCreateResponse:
            response = TasksCreateResponse(
                tasks=[
                    TaskCreateResponse(
                        name="Map customer segments",
                        content="List 3-5 likely segments and pains.",
                    ),
                    TaskCreateResponse(
                        name="Define value prop tests",
                        content="Draft 3 hypotheses and validation steps.",
                    ),
                ]
            )
            return TaskResult(
                messages=[StructuredMessage(content=response, source=system3.name)]
            )
        if output_content_type is TasksAssignResponse:
            initiative_id = chat_messages[-1].initiative_id
            db = next(get_db())
            rows = (
                db.query(Task)
                .filter(
                    Task.team_id == team_id,
                    Task.initiative_id == initiative_id,
                )
                .all()
            )
            db.close()
            assignments = [(system1_id, row.id) for row in rows]
            response = TasksAssignResponse(assignments=assignments)
            return TaskResult(
                messages=[StructuredMessage(content=response, source=system3.name)]
            )
        return TaskResult(
            messages=[TextMessage(content="Assigning tasks.", source=system3.name)]
        )

    async def system1_run(
        chat_messages, ctx, message_specific_prompts=None, output_content_type=None
    ):
        return TaskResult(
            messages=[TextMessage(content="Completed task.", source=system1.name)]
        )

    system4_to_system3_called = {"count": 0}

    async def route_system4_message(message, agent_id):
        system4_to_system3_called["count"] += 1
        ctx = MessageContext(
            sender=system4.agent_id,
            topic_id=None,
            is_rpc=False,
            cancellation_token=CancellationToken(),
            message_id="system4_to_system3",
        )
        await system3.handle_initiative_assign_message(
            message=message,
            ctx=ctx,
        )  # type: ignore[call-arg]

    system3_to_system1_called = {"count": 0}

    async def route_system3_message(message, agent_id):
        system3_to_system1_called["count"] += 1
        ctx = MessageContext(
            sender=system3.agent_id,
            topic_id=None,
            is_rpc=False,
            cancellation_token=CancellationToken(),
            message_id="system3_to_system1",
        )
        await system1.handle_assign_task_message(
            message=message,
            ctx=ctx,
        )  # type: ignore[call-arg]

    collected_reviews: list = []

    async def capture_system1_message(message, agent_id):
        collected_reviews.append(message)
        return None

    monkeypatch.setattr(system4, "run", system4_run)
    monkeypatch.setattr(system3, "run", system3_run)
    monkeypatch.setattr(system1, "run", system1_run)
    monkeypatch.setattr(system3, "_was_tool_called", lambda response, tool_name: False)
    monkeypatch.setattr(system4, "_publish_message_to_agent", route_system4_message)
    monkeypatch.setattr(system3, "_publish_message_to_agent", route_system3_message)
    monkeypatch.setattr(system1, "_publish_message_to_agent", capture_system1_message)

    async def answer_questions() -> None:
        while True:
            pending = get_pending_question()
            if pending is None:
                await asyncio.sleep(0)
                continue
            if "outcome" in pending.content:
                resolve_pending_question("Validate market fit quickly.")
            elif "persona" in pending.content:
                resolve_pending_question("Solo technical founders.")
                return
            await asyncio.sleep(0)

    answer_task = asyncio.create_task(answer_questions())

    user_message = UserMessage(content=TEST_PROMPT, source="User")
    ctx = MessageContext(
        sender=AgentId.from_str("User/root"),
        topic_id=None,
        is_rpc=False,
        cancellation_token=CancellationToken(),
        message_id="user_prompt",
    )
    await system4.handle_user_message(
        message=user_message,
        ctx=ctx,
    )  # type: ignore[call-arg]
    await answer_task

    db = next(get_db())
    try:
        assert system4_to_system3_called["count"] == 1
        assert system3_to_system1_called["count"] >= 1
        tasks = db.query(Task).filter(Task.team_id == team_id).all()
        assert tasks
        assert all(task.status == Status.COMPLETED for task in tasks)
        assert all(task.assignee == "System1/ops1" for task in tasks)
        assert len(collected_reviews) == len(tasks)
    finally:
        db.close()
