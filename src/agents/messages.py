from autogen_agentchat.messages import BaseTextChatMessage
from pydantic import BaseModel, ConfigDict


class InvalidReviewRecoveryContract(BaseModel):
    """Contract payload for invalid TaskReview recovery escalation to System5."""

    model_config = ConfigDict(extra="forbid")

    task_id: int
    initiative_id: int | None
    observed_status: str
    retry_count: int
    retry_limit: int
    error_summary: str
    next_action: str


class BlockedRemediationContract(BaseModel):
    """Contract payload for blocked-task remediation requests to System5."""

    model_config = ConfigDict(extra="forbid")

    task_id: int
    initiative_id: int | None
    assignee_agent_id_str: str
    blocked_reasoning: str
    remediation_request: str


class RejectedReplacementContract(BaseModel):
    """Contract payload for rejected-task replacement/remediation with System5."""

    model_config = ConfigDict(extra="forbid")

    task_id: int
    initiative_id: int | None
    assignee_agent_id_str: str
    policy_id: int
    policy_reasoning: str
    case_judgement: str | None
    execution_log: str | None
    requested_outcome: str


class UserMessage(BaseTextChatMessage):
    """Used by user to communicate with System 4."""

    content: str


class ReplyUserMessage(BaseTextChatMessage):
    """Used by System 4 to understand the systems user better, or forward information to the user."""

    content: str


class TaskAssignMessage(BaseTextChatMessage):
    """Used by System 3 to assign a task to a System 1."""

    task_id: int
    assignee_agent_id_str: str


class TaskReviewMessage(BaseTextChatMessage):
    """Used by System 1 to request a review of a task by system 3."""

    task_id: int
    assignee_agent_id_str: str


class CapabilityGapMessage(BaseTextChatMessage):
    """Used by System 1 to inform System 3 of unability to complete a task and by System 3 to inform System 5 that instance is unable to complete a task."""

    task_id: int
    content: str
    assignee_agent_id_str: str
    contract: BlockedRemediationContract | None = None


class InitiativeAssignMessage(BaseTextChatMessage):
    """Used by System 4 to assign a project to System 3."""

    initiative_id: int


class InitiativeReviewMessage(BaseTextChatMessage):
    """Used by System 3 to request a review of a project by System 4."""

    initiative_id: int


class PolicyViolationMessage(BaseTextChatMessage):
    """Used by System 3 to inform System 5 that a System 1 has violated a policy while completing a task."""

    task_id: int
    policy_id: int
    assignee_agent_id_str: str
    content: str
    contract: RejectedReplacementContract | None = None


class PolicyVagueMessage(BaseTextChatMessage):
    """Used by System 3 to request clarification of a policy, from System 5 in regards to a specific task."""

    task_id: int
    policy_id: int
    content: str


class PolicySuggestionMessage(BaseTextChatMessage):
    """Used by System 3 and System 4 to suggest a policy change to System 5."""

    policy_id: int | None
    task_id: int | None = None
    content: str


class StrategyRequestMessage(BaseTextChatMessage):
    """Used by System 5 to request a strategy from System 4for achieving the instance purpose."""

    content: str


class StrategyReviewMessage(BaseTextChatMessage):
    """Used by System 4 to request a review of a strategy by System 5."""

    strategy_id: int


class ResearchRequestMessage(BaseTextChatMessage):
    """Used by System 5 to request a research into the environment from System 4. This could be to resolve a capability gap."""

    content: str


class ResearchReviewMessage(BaseTextChatMessage):
    """Used by System 4 to request a review of a research by System 5."""

    content: str


class TeamEnvelopeUpdateMessage(BaseTextChatMessage):
    """Used to request team envelope skill updates from System 5."""

    team_id: int
    skill_name: str
    action: str
    content: str


class SystemSkillGrantUpdateMessage(BaseTextChatMessage):
    """Used to request system skill grant updates from System 5."""

    system_id: int
    skill_name: str
    action: str
    content: str


class RecursionCreateMessage(BaseTextChatMessage):
    """Used to request creation of a recursion linkage by System 5."""

    sub_team_id: int
    origin_system_id: int
    parent_team_id: int
    content: str


class ConfirmationMessage(BaseTextChatMessage):
    """Used by a system to confirm an action has been completed."""

    content: str
    is_error: bool


class ConfirmationResponse(BaseModel):
    """Structured-output payload for providers.

    We intentionally avoid inheriting from BaseTextChatMessage because upstream
    includes a free-form `metadata` object that some OpenAI-compatible providers
    reject unless every object schema sets `additionalProperties: false`.

    Using a plain BaseModel with `extra='forbid'` yields a stricter JSON schema.
    """

    model_config = ConfigDict(extra="forbid")

    content: str
    is_error: bool


class InternalErrorMessage(BaseTextChatMessage):
    """Used by systems to route internal processing failures to the team's System5."""

    team_id: int
    origin_system_id_str: str
    failed_message_type: str
    error_summary: str
    task_id: int | None = None
    contract: InvalidReviewRecoveryContract | None = None
