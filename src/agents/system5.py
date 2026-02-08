from autogen_agentchat.base import TaskResult
from autogen_core import MessageContext, message_handler
from autogen_core.tools import FunctionTool

from src.agents.messages import (
    CapabilityGapMessage,
    ConfirmationMessage,
    PolicySuggestionMessage,
    TaskReviewMessage,
    PolicyVagueMessage,
    PolicyViolationMessage,
    RecursionCreateMessage,
    ResearchReviewMessage,
    StrategyReviewMessage,
    SystemSkillGrantUpdateMessage,
    TeamEnvelopeUpdateMessage,
)
from src.agents.system_base import SystemBase
from src.cyberagent.services import policies as policy_service
from src.cyberagent.services import procedures as procedures_service
from src.cyberagent.db.models.system import get_system_from_agent_id
from src.cyberagent.services import recursions as recursions_service
from src.cyberagent.services import strategies as strategy_service
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import tasks as task_service
from src.cyberagent.services import teams as teams_service
from src.enums import SystemType


class System5(SystemBase):
    def __init__(self, name: str, trace_context: dict | None = None):
        super().__init__(
            name,
            identity_prompt="""
            You are the Policy and Identity system responsible for maintaining the organization's identity,
            making policy decisions, and ensuring overall system viability. You balance the immediate operational
            needs (System 3) with long-term strategic requirements (System 4) to maintain organizational cohesion.
            Your decisions shape the future of the organization while preserving its core identity and values.
            """,
            responsibility_prompts=[
                "1. Policy Management: Create, update, and enforce organizational policies that govern all system operations.",
                "2. Conflict Resolution: Resolve conflicts between System 3 (operations) and System 4 (strategy) to maintain harmony.",
                "3. Resource Allocation: Make strategic decisions on resource distribution across all systems based on organizational priorities.",
                "4. System Evolution: Evaluate and approve changes to system structure, capabilities, and organizational design.",
                "5. Identity Maintenance: Ensure the system maintains its core identity, purpose, and values across all operations and evolution.",
            ],
            trace_context=trace_context,
        )
        self.available_tools = [
            FunctionTool(
                self.approve_procedure_tool,
                "Approve a draft procedure version and retire the prior approved version.",
            )
        ]
        self.tools = self.available_tools

    @message_handler
    async def handle_capability_gap_message(
        self, message: CapabilityGapMessage, context: MessageContext
    ) -> ConfirmationMessage:
        """
        Handle capability gaps identified by System3 or System4.

        Analyzes the capability gap, determines if existing tools can address it,
        and decides whether to request research from System4 or approve system evolution.
        """
        message_specific_prompts = [
            "## CAPABILITY GAP ANALYSIS",
            "You have received a capability gap report from a system that cannot complete its assigned task.",
            "## ANALYSIS REQUIREMENTS",
            "1. Assess the nature and severity of the capability gap.",
            "2. Determine if existing tools or policies can address this gap.",
            "3. If no existing solutions are available, consider:",
            "   - Requesting research from System4 using ResearchRequestMessage",
            "   - Approving system evolution to add new capabilities",
            "   - Modifying existing policies to accommodate the requirement",
            "4. Make a decision that balances immediate operational needs with long-term viability.",
            "## RESPONSE FORMAT",
            "Respond with a ConfirmationMessage indicating your decision and any actions taken.",
        ]

        raise NotImplementedError(
            "Missing policy modification tools & permission tools here."
        )

        response = await self.run(
            [message],
            context,
            message_specific_prompts,
            output_content_type=ConfirmationMessage,
        )

        return self._get_structured_message(response, ConfirmationMessage)

    @message_handler
    async def handle_policy_violation_message(
        self, message: PolicyViolationMessage, context: MessageContext
    ) -> ConfirmationMessage:
        """
        Handle policy violations reported by System3.

        Reviews the violation details and determines appropriate action,
        which may include policy clarification, system modification, or other corrective measures.
        """
        message_specific_prompts = [
            "## POLICY VIOLATION REVIEW",
            "System3 has reported a policy violation that requires your attention.",
            "## REVIEW REQUIREMENTS",
            "1. Examine the details of the policy violation.",
            "2. Determine if this is a genuine violation or a policy interpretation issue.",
            "3. If it's a genuine violation, decide on appropriate corrective action:",
            "   - Policy clarification and re-education",
            "   - System modification to prevent recurrence",
            "   - Disciplinary action if intentional",
            "4. If it's an interpretation issue, provide clarification to System3.",
            "5. Document your decision and any actions taken.",
            "## RESPONSE FORMAT",
            "Respond with a ConfirmationMessage detailing your decision and resolution.",
        ]

        raise NotImplementedError("Missing policy modification tools here.")

        response = await self.run(
            [message],
            context,
            message_specific_prompts,
            output_content_type=ConfirmationMessage,
        )

        return self._get_structured_message(response, ConfirmationMessage)

    def approve_procedure_tool(self, procedure_id: int) -> dict[str, object]:
        """
        Approve a procedure draft version.
        """
        system = get_system_from_agent_id(self.agent_id.__str__())
        if system is None:
            raise ValueError("System record not found for this agent.")
        procedure = procedures_service.approve_procedure(
            procedure_id=procedure_id, approved_by_system_id=system.id
        )
        return {
            "procedure_id": procedure.id,
            "version": procedure.version,
            "status": procedure.status.value,
        }

    @message_handler
    async def handle_policy_vague_message(
        self, message: PolicyVagueMessage, context: MessageContext
    ) -> ConfirmationMessage:
        """
        Clarify ambiguous policies for System3.

        Analyzes the ambiguous policy and provides clarification or updates the policy
        to resolve the ambiguity, then communicates the resolution back to System3.
        """
        task = task_service.get_task_by_id(message.task_id)
        policy = policy_service.get_policy_by_id(message.policy_id)
        message_specific_prompts = [
            "## POLICY CLARIFICATION REQUEST",
            "System3 has requested clarification on a policy that is unclear or ambiguous.",
            "## DETAILS",
            *task.to_prompt(),
            *policy.to_prompt(),
            "## CLARIFICATION REQUIREMENTS",
            "1. Review the policy in question and identify sources of ambiguity.",
            "2. Determine if the policy needs:",
            "   - Simple clarification and explanation",
            "   - Complete rewrite for better clarity",
            "   - Additional examples or guidelines",
            "3. If clarification is sufficient, provide clear guidance to System3.",
            "4. If rewrite is needed, use the update_policy_tool to modify the policy.",
            "5. Ensure the clarified policy maintains organizational intent and values.",
            "## RESPONSE FORMAT",
            "Respond with a ConfirmationMessage containing the clarification or policy update.",
        ]

        response = await self.run(
            [message],
            context,
            message_specific_prompts,
            output_content_type=ConfirmationMessage,
        )

        return self._get_structured_message(response, ConfirmationMessage)

    @message_handler
    async def handle_policy_suggestion_message(
        self, message: PolicySuggestionMessage, context: MessageContext
    ) -> ConfirmationMessage:
        """
        Review and approve/reject policy change suggestions from System3 or System4.

        Carefully evaluates the reasoning behind policy change suggestions and
        makes decisions that balance innovation with organizational stability.
        """
        if message.task_id is not None and message.policy_id is None:
            task = task_service.get_task_by_id(message.task_id)
            if not task.assignee:
                return ConfirmationMessage(
                    content=f"Task {task.id} has no assignee; cannot bootstrap policies.",
                    is_error=True,
                    source=self.name,
                )
            created = policy_service.ensure_baseline_policies_for_assignee(
                task.assignee
            )
            control_systems = self._get_systems_by_type(SystemType.CONTROL)
            if control_systems:
                await self._publish_message_to_agent(
                    TaskReviewMessage(
                        task_id=task.id,
                        assignee_agent_id_str=task.assignee,
                        source=self.name,
                        content=task.result or task.name,
                    ),
                    control_systems[0].get_agent_id(),
                )
            return ConfirmationMessage(
                content=(
                    f"Created {created} baseline policies and retriggered "
                    f"task review for task {task.id}."
                ),
                is_error=False,
                source=self.name,
            )

        policy_prompt = []
        if message.policy_id:
            policy = policy_service.get_policy_by_id(message.policy_id)
            if policy is not None:
                policy_prompt = policy.to_prompt()
        message_specific_prompts = [
            "## POLICY SUGGESTION REVIEW",
            "You have received a policy change suggestion from another system.",
            "## SUGGESTION DETAILS",
            *policy_prompt,
            f"Content: {message.content}",
            "## EVALUATION REQUIREMENTS",
            "1. Carefully review the suggested policy change.",
            "2. Assess the reasoning and justification provided.",
            "3. Evaluate the potential impact on:",
            "   - Organizational identity and core values",
            "   - Operational efficiency and effectiveness",
            "   - Compliance and risk management",
            "   - Long-term strategic goals",
            "4. Consider alternatives or modifications to the suggestion.",
            "5. Make a decision to approve, reject, or modify the suggestion.",
            "## RESPONSE FORMAT",
            "Respond with a ConfirmationMessage indicating your decision and rationale.",
        ]

        response = await self.run([message], context, message_specific_prompts)
        return self._confirmation_from_response(response)

    def _confirmation_from_response(
        self, response: "TaskResult"
    ) -> ConfirmationMessage:
        last_message = self._get_last_message(response)
        content = (
            last_message.to_model_text()
            if hasattr(last_message, "to_model_text")
            else last_message.to_text()
        )
        return ConfirmationMessage(content=content, is_error=False, source=self.name)

    @message_handler
    async def handle_strategy_review_message(
        self, message: StrategyReviewMessage, context: MessageContext
    ) -> ConfirmationMessage:
        """
        Review strategies from System4.

        Evaluates strategy alignment with organizational identity and makes
        decisions to approve, reject, or request modifications to strategies.
        """
        strategy = strategy_service.get_strategy(message.strategy_id)
        message_specific_prompts = [
            "## STRATEGY REVIEW",
            "System4 has submitted a strategy for your review and approval.",
            "## STRATEGY DETAILS",
            *strategy.to_prompt(),
            "### INITIATIVES",
            *[initiative.to_prompt() for initiative in strategy.get_initiatives()],
            "## EVALUATION REQUIREMENTS",
            "1. Examine the strategy in detail.",
            "2. Assess alignment with organizational identity and core values.",
            "3. Evaluate feasibility and resource requirements.",
            "4. Consider long-term impact on organizational viability.",
            "5. Determine if the strategy:",
            "   - Should be approved as-is",
            "   - Needs modifications before approval",
            "   - Should be rejected with reasoning",
            "## RESPONSE FORMAT",
            "Respond with a ConfirmationMessage containing your decision and feedback.",
        ]

        response = await self.run(
            [message],
            context,
            message_specific_prompts,
            output_content_type=ConfirmationMessage,
        )

        return self._get_structured_message(response, ConfirmationMessage)

    @message_handler
    async def handle_research_review_message(
        self, message: ResearchReviewMessage, context: MessageContext
    ) -> ConfirmationMessage:
        """
        Review research results from System4.

        Evaluates research findings and determines if new policies or system
        changes are needed based on the research outcomes.
        """
        message_specific_prompts = [
            "## RESEARCH REVIEW",
            "System4 has completed research and submitted findings for your review.",
            "## RESEARCH DETAILS",
            f"Content: {message.content}",
            "## EVALUATION REQUIREMENTS",
            "1. Review the research findings thoroughly.",
            "2. Assess the quality and reliability of the research.",
            "3. Determine if the findings suggest:",
            "   - New policies are needed",
            "   - Existing policies should be updated",
            "   - System capabilities need enhancement",
            "   - Strategic direction should change",
            "4. Consider the impact on organizational identity and viability.",
            "5. Make decisions on what actions to take based on the research.",
            "## RESPONSE FORMAT",
            "Respond with a ConfirmationMessage detailing your decisions and next steps.",
        ]

        response = await self.run(
            [message],
            context,
            message_specific_prompts,
            output_content_type=ConfirmationMessage,
        )

        return self._get_structured_message(response, ConfirmationMessage)

    @message_handler
    async def handle_team_envelope_update_message(
        self, message: TeamEnvelopeUpdateMessage, context: MessageContext
    ) -> ConfirmationMessage:
        """
        Handle team envelope skill updates within the active team.
        """
        if message.team_id != self.team_id:
            return ConfirmationMessage(
                content=(
                    f"System5 cannot modify team {message.team_id} from team {self.team_id}."
                ),
                is_error=True,
                source=self.agent_id.__str__(),
            )

        if message.action == "add":
            teams_service.add_allowed_skill(
                team_id=message.team_id,
                skill_name=message.skill_name,
                actor_id=self.agent_id.__str__(),
            )
            return ConfirmationMessage(
                content=f"Added skill {message.skill_name} to team {message.team_id}.",
                is_error=False,
                source=self.agent_id.__str__(),
            )

        if message.action == "remove":
            revoked = teams_service.remove_allowed_skill(
                team_id=message.team_id,
                skill_name=message.skill_name,
                actor_id=self.agent_id.__str__(),
            )
            return ConfirmationMessage(
                content=(
                    f"Removed skill {message.skill_name} from team {message.team_id}. "
                    f"Revoked {revoked} grants."
                ),
                is_error=False,
                source=self.agent_id.__str__(),
            )

        return ConfirmationMessage(
            content=f"Unknown team envelope action '{message.action}'.",
            is_error=True,
            source=self.agent_id.__str__(),
        )

    @message_handler
    async def handle_system_skill_grant_update_message(
        self, message: SystemSkillGrantUpdateMessage, context: MessageContext
    ) -> ConfirmationMessage:
        """
        Handle system skill grant updates within the active team.
        """
        system = systems_service.get_system(message.system_id)
        if system is None:
            return ConfirmationMessage(
                content=f"System id {message.system_id} is not registered.",
                is_error=True,
                source=self.agent_id.__str__(),
            )
        if system.team_id != self.team_id:
            return ConfirmationMessage(
                content=(
                    f"System5 cannot modify system {message.system_id} in team "
                    f"{system.team_id} from team {self.team_id}."
                ),
                is_error=True,
                source=self.agent_id.__str__(),
            )

        if message.action == "add":
            try:
                systems_service.add_skill_grant(
                    system_id=message.system_id,
                    skill_name=message.skill_name,
                    actor_id=self.agent_id.__str__(),
                )
            except PermissionError as exc:
                return ConfirmationMessage(
                    content=str(exc),
                    is_error=True,
                    source=self.agent_id.__str__(),
                )
            return ConfirmationMessage(
                content=(
                    f"Granted skill {message.skill_name} to system {message.system_id}."
                ),
                is_error=False,
                source=self.agent_id.__str__(),
            )

        if message.action == "remove":
            systems_service.remove_skill_grant(
                system_id=message.system_id,
                skill_name=message.skill_name,
                actor_id=self.agent_id.__str__(),
            )
            return ConfirmationMessage(
                content=(
                    f"Revoked skill {message.skill_name} from system {message.system_id}."
                ),
                is_error=False,
                source=self.agent_id.__str__(),
            )

        return ConfirmationMessage(
            content=f"Unknown system grant action '{message.action}'.",
            is_error=True,
            source=self.agent_id.__str__(),
        )

    @message_handler
    async def handle_recursion_create_message(
        self, message: RecursionCreateMessage, context: MessageContext
    ) -> ConfirmationMessage:
        """
        Handle recursion linkage creation within the active team.
        """
        if message.parent_team_id != self.team_id:
            return ConfirmationMessage(
                content=(
                    f"System5 cannot create recursion for team {message.parent_team_id} "
                    f"from team {self.team_id}."
                ),
                is_error=True,
                source=self.agent_id.__str__(),
            )

        try:
            recursions_service.create_recursion(
                sub_team_id=message.sub_team_id,
                origin_system_id=message.origin_system_id,
                parent_team_id=message.parent_team_id,
                actor_id=self.agent_id.__str__(),
            )
        except ValueError as exc:
            return ConfirmationMessage(
                content=str(exc),
                is_error=True,
                source=self.agent_id.__str__(),
            )

        return ConfirmationMessage(
            content=(
                f"Created recursion link for sub_team {message.sub_team_id} "
                f"from origin system {message.origin_system_id}."
            ),
            is_error=False,
            source=self.agent_id.__str__(),
        )
