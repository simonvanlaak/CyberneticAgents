from typing import List, Tuple

from autogen_agentchat.messages import TextMessage
from autogen_core import MessageContext, message_handler
from autogen_core.tools import FunctionTool
from pydantic import BaseModel

from src.agent_utils import get_user_agent_id
from src.agents.messages import (
    ConfirmationMessage,
    InitiativeAssignMessage,
    InitiativeReviewMessage,
    PolicySuggestionMessage,
    ResearchRequestMessage,
    ResearchReviewMessage,
    StrategyRequestMessage,
    UserMessage,
)
from src.agents.system_base import SystemBase
from src.enums import SystemType
from src.models.initiative import Initiative, get_initiative
from src.models.purpose import get_or_create_default_purpose
from src.models.strategy import Strategy, get_strategy, get_teams_active_strategy
from src.models.system import get_system, get_system_by_type
from src.tools.contact_user import ContactUserTool, InformUserTool


class InitiativeCreateResponse(BaseModel):
    name: str
    description: str


class StrategyCreateResponse(BaseModel):
    """Response containing created strategy and initiatives."""

    name: str
    description: str
    initiatives: List[InitiativeCreateResponse]


class InitiativeAdjustResponse(BaseModel):
    id: int
    name: str
    description: str


class StrategyAdjustResponse(BaseModel):
    name: str | None
    description: str | None
    initiatives: List[InitiativeAdjustResponse]


class InitiativeAssignResponse(BaseModel):
    initiative_id: int | None


class ResearchResultsResponse(BaseModel):
    """Response containing research findings."""

    findings: str
    sources: List[str]
    recommendations: List[str]


class System4(SystemBase):
    def __init__(self, name: str, trace_context: dict | None = None):
        # Convert the name to the correct AgentId format
        # If name is just "root", we need to create "System4/root"
        if "/" not in name:
            agent_id_str = f"{self.__class__.__name__}/{name}"
        else:
            agent_id_str = name
        super().__init__(
            agent_id_str,
            identity_prompt="""
            You are the Intelligence and Development system responsible for strategic planning,
            environmental scanning, and long-term innovation. You analyze the external environment,
            identify opportunities and threats, and develop strategies to achieve the system's purpose.
            """,
            responsibility_prompts=[
                "1. Environmental Scanning: Monitor external environment for changes and opportunities.",
                "2. Strategic Planning: Develop and refine strategies to achieve the system's purpose.",
                "3. Innovation Management: Identify and propose new initiatives and improvements.",
                "4. User Interaction: Handle user communications and gather requirements.",
                "5. Research Coordination: Conduct research to address capability gaps and inform strategy.",
            ],
            trace_context=trace_context,
        )
        # Register system specific tools
        self.available_tools.extend(
            [
                FunctionTool(
                    self.suggest_policy_tool,
                    "Suggest policies to System 5 to address capability gaps and inform strategy.",
                ),
                FunctionTool(
                    self.create_strategy_tool,
                    "Trigger yourself to create a strategy. Returns True when message was successfuly sent, or False with Exception that was thrown.",
                ),
                FunctionTool(
                    self.review_initiative_tool,
                    "Trigger yourself to review an existing initiative. Returns True when message was successfuly sent, or False with Exception that was thrown.",
                ),
            ]
        )
        if not any(tool.name == ContactUserTool.__name__ for tool in self.available_tools):
            self.available_tools.append(ContactUserTool(self.agent_id))
        if not any(tool.name == InformUserTool.__name__ for tool in self.available_tools):
            self.available_tools.append(InformUserTool(self.agent_id))
        self.tools = self.available_tools

    @message_handler
    async def handle_user_message(
        self, message: UserMessage, ctx: MessageContext
    ) -> None:
        """Handle user communications and determine impact on strategies."""
        if ctx.sender is None:
            raise ValueError()
        message_specific_prompts = [
            "## USER COMMUNICATION",
            "You have received a message from the user. Analyze the content and determine:",
            "1. Does this impact any existing strategies or initiatives?",
            "2. Does this represent a new high-priority initiative?",
            "3. Does this provide significant new information about the environment?",
            "4. Are there any follow-up questions needed for clarification?",
            "## USER MESSAGE",
            message.content,
            "## CURRENT STRATEGY",
            *(
                get_teams_active_strategy(self.team_id).to_prompt()
                if get_teams_active_strategy(self.team_id)
                else ["No active strategy found."]
            ),
            "## ASSIGNMENT",
            "Analyze the user message and respond appropriately. If follow-up questions are needed, "
            f"If this message signals a signifies a significant change of environment or the expectations of this system, use the {self.suggest_policy_tool.__name__} to inform the System5 of the changes."
            f"If this impacts strategies or represents new initiatives, use the {self.create_strategy_tool.__name__} tool to create a new strategy.",
            f"If this impacts the current strategy significantly, use the {self.review_initiative_tool.__name__} tool to review existing initiatives for needed change.",
            f"Suggest how current policies should be changed in order to adjust strategies. Use the {self.suggest_policy_tool.__name__} for that.",
            "If the user would like to get insights on existing strategies or status, inform them.",
            f"If you want to ask the user a question, use the {ContactUserTool.__name__}.",
            f"If you want to inform the user about progress or status, use the {InformUserTool.__name__}.",
        ]

        await self.run([message], ctx, message_specific_prompts)

    @message_handler
    async def handle_strategy_request_message(
        self, message: StrategyRequestMessage, ctx: MessageContext
    ) -> ConfirmationMessage | None:
        """Create strategy to implement the instance's purpose."""
        # Break down strategy into initiatives
        message_specific_prompts = [
            "## STRATEGY DEVELOPMENT REQUEST",
            "You have been tasked with creating a strategy to achieve the system's purpose.",
            "## PURPOSE DESCRIPTION",
            message.content,
        ]
        create_stategy_prompts = message_specific_prompts
        create_stategy_prompts.extend(
            [
                "## ASSIGNMENT",
                "1. Research best practices and approaches for achieving this purpose.",
                "2. Break down the purpose into strategic objectives.",
                "3. Create initiatives to achieve each objective.",
                "4. Prioritize initiatives based on impact and feasibility.",
            ]
        )

        response = await self.run(
            [message],
            ctx,
            create_stategy_prompts,
            output_content_type=StrategyCreateResponse,
        )
        strategy_response = self._get_structured_message(
            response, StrategyCreateResponse
        )
        purpose = get_or_create_default_purpose(self.team_id)
        strategy = Strategy(
            team_id=self.team_id,
            purpose_id=purpose.id,
            name=strategy_response.name,
            description=strategy_response.description,
            result="",
        )
        strategy_id = strategy.add()
        initiatives = []
        for initiative_response in strategy_response.initiatives:
            initiative = Initiative(
                team_id=self.team_id,
                name=initiative_response.name,
                description=initiative_response.description,
                strategy_id=strategy_id,
            )
            initiative.add()
            initiatives.append(initiative)

        try:
            initiative = await self._select_next_initiative(
                message, ctx, message_specific_prompts, strategy
            )
        except Exception:
            initiative = initiatives[0] if initiatives else None

        if initiative is None:
            raise ValueError("No initiatives available to assign.")

        await self._publish_message_to_agent(
            initiative.get_assign_message(),
            get_system_by_type(self.team_id, SystemType.CONTROL).get_agent_id(),
        )
        return ConfirmationMessage(
            content=f"Initiative {initiative.name}:{initiative.description} started.",
            is_error=False,
            source=self.name,
        )

    @message_handler
    async def handle_initiative_review_message(
        self, message: InitiativeReviewMessage, ctx: MessageContext
    ) -> InitiativeAssignMessage | None:
        """Review completed initiatives and adjust strategies."""
        # Fetch initiative from database using initiative_id
        initiative = get_initiative(message.initiative_id)
        if not initiative:
            raise ValueError(f"Initiative with id {message.initiative_id} not found")

        current_strategy = get_strategy(initiative.strategy_id)
        message_specific_prompts = [
            "## INITIATIVE REVIEW",
            "An initiative has been completed by System3. Review the results and determine:",
            "1. Was the initiative successful in achieving its objectives?",
            "2. What lessons can be learned from this initiative?",
            "3. Should the overall strategy be adjusted based on these results?",
            "4. Are there other initiatives that should be prioritized next?",
            "## COMPLETED INITIATIVE",
            *initiative.to_prompt(),
        ]

        # Check for strategy adjustments
        strategy_adjustments = message_specific_prompts + [
            "## CURRENT STRATEGY",
            *current_strategy.to_prompt(),
            "## Assignment",
            "Review the results from the completed initiative and determine:",
            "1. Was the initiative successful in achieving its objectives?",
            "2. What lessons can be learned from this initiative?",
            "3. Should the overall strategy be adjusted based on these results?",
            "## RESPONSE",
            "If the overall strategy needs to be adjusted, respond with the adjusted initiaives.",
            "If you want to change the strategies name or descriptions, also set these values, otherwise set them no None.",
        ]

        response = await self.run(
            [message], ctx, strategy_adjustments, StrategyAdjustResponse
        )
        strategy_adjustments = self._get_structured_message(
            response, StrategyAdjustResponse
        )
        if strategy_adjustments.name:
            current_strategy.name = strategy_adjustments.name
        if strategy_adjustments.description:
            current_strategy.description = strategy_adjustments.description
        current_strategy.update()
        if len(strategy_adjustments.initiatives) > 0:
            for initiative_adjustment in strategy_adjustments.initiatives:
                initiative = get_initiative(initiative_adjustment.id)
                if initiative_adjustment.name:
                    initiative.name = initiative_adjustment.name
                if initiative_adjustment.description:
                    initiative.description = initiative_adjustment.description
                initiative.update()

        # Check for significant knowledge gained and pass to system 5
        get_user_input = message_specific_prompts + [
            "## CURRENT STRATEGY",
            *current_strategy.to_prompt(),
            "## ASSIGNMENT",
            f"Identify if any results from the completed initiative contain significant new knowledge gained."
            f"If this is the case develop policy suggestions and use the {self.suggest_policy_tool.__name__} tool to forward them to System 5."
            "## RESPONSE",
            "Do not respond.",
        ]
        response = await self.run([message], ctx, get_user_input)
        # Assign next initiative
        initiative = await self._select_next_initiative(
            message, ctx, message_specific_prompts, current_strategy
        )
        return initiative.get_assign_message()

    @message_handler
    async def handle_research_request_message(
        self, message: ResearchRequestMessage, ctx: MessageContext
    ) -> ResearchReviewMessage:
        """Conduct research to address capability gaps."""
        message_specific_prompts = [
            "## RESEARCH REQUEST",
            "System5 has requested research to address a capability gap.",
            "## RESEARCH TOPIC",
            message.content,
            "## ASSIGNMENT",
            "1. Use available research tools to gather information about this topic.",
            "2. Analyze existing tools and solutions that could address this gap.",
            "3. If no existing solutions are found, consider proposing a development initiative.",
            "4. Document findings, sources, and recommendations.",
            "5. Use the conduct_research_tool to formalize the research results.",
        ]
        response = await self.run(
            [message], ctx, message_specific_prompts, ResearchResultsResponse
        )
        research_response = self._get_structured_message(
            response, ResearchResultsResponse
        )
        return ResearchReviewMessage(
            content=research_response.findings, source=self.name
        )

    async def assign_initiative_tool(self, initiative_id: int, system3_id: int):
        """Assign initiative to System3 for execution."""
        await self._publish_message_to_agent(
            get_initiative(initiative_id).get_assign_message(),
            get_system(system3_id).get_agent_id(),
        )

    async def suggest_policy_tool(self, policy_id: int, suggestion: str):
        await self._publish_message_to_agent(
            PolicySuggestionMessage(
                policy_id=policy_id, content=suggestion, source=self.name
            ),
            get_system_by_type(self.team_id, SystemType.POLICY).get_agent_id(),
        )

    async def contact_user_tool(self, content: str, wait_for_response: bool = False):
        try:
            if wait_for_response:
                await self.send_message(
                    TextMessage(content=content, source=self.name), get_user_agent_id()
                )
            else:
                await self._publish_message_to_agent(
                    TextMessage(content=content, source=self.name), get_user_agent_id()
                )
            return (True, None)
        except Exception as e:
            return (False, e)

    async def create_strategy_tool(self, content: str) -> Tuple[bool, Exception | None]:
        try:
            await self._publish_message_to_agent(
                StrategyRequestMessage(source=self.name, content=content), self.id
            )
            return (True, None)
        except Exception as e:
            return (False, e)

    async def review_initiative_tool(
        self, initiative_id: int, content: str
    ) -> Tuple[bool, Exception | None]:
        try:
            await self._publish_message_to_agent(
                InitiativeReviewMessage(
                    source=self.name, content=content, initiative_id=initiative_id
                ),
                self.id,
            )
            return (True, None)
        except Exception as e:
            return (False, e)

    async def _select_next_initiative(
        self, message, ctx, prompts, strategy: Strategy
    ) -> Initiative:
        # Identify initative to start first
        assign_initiative_prompts = prompts + [
            "## STRATEGY",
            *strategy.to_prompt(),
            "## INITIATIVES",
            *[initiative.to_prompt() for initiative in strategy.get_initiatives()],
            "## ASSIGNMENT",
            "Assign highest priority initiative to be started.",
            "## RESPONSE",
            "Reply with the id of the iniative to start, or with None if there are no initiatives to start",
        ]
        response = await self.run(
            [message],
            ctx,
            assign_initiative_prompts,
            output_content_type=InitiativeAssignResponse,
        )
        initiative_response = self._get_structured_message(
            response, InitiativeAssignResponse
        )
        if not initiative_response.initiative_id:
            # Here we would probably need to send a message either to Sytem 5 or the user.
            raise NotImplementedError()
        # Instruct System 3 to start the initiative
        return strategy.get_initiative(initiative_response.initiative_id)
