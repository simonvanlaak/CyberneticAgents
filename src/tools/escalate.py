import uuid

from autogen_agentchat.messages import HandoffMessage
from autogen_core import AgentId, CancellationToken
from autogen_core.models import FunctionExecutionResult
from opentelemetry import trace
from pydantic import BaseModel

from src.rbac.system_types import SystemTypes
from src.tools.rbac_base_tool import RBACBaseTool


class EscalateArgsType(BaseModel):
    target_system_id: str
    content: str


class Escalate(RBACBaseTool):
    def __init__(self, agent_id: AgentId):
        description = (
            "Escalate an issue to another system via the runtime."
            "Use this when you cannot resolve an issue yourself."
        )
        super().__init__(
            agent_id=agent_id,
            args_type=EscalateArgsType,
            tool_name=self.__class__.__name__,
            description=description,
        )

    async def run(
        self, args: EscalateArgsType, cancellation_token: CancellationToken
    ) -> FunctionExecutionResult:
        """Escalate an issue to another agent via the runtime."""
        print(f"[{self.agent_id.key}/{self.tool_name}] {args}")
        call_id = uuid.uuid4().hex
        try:
            if not self.is_action_allowed(args.target_system_id):
                return FunctionExecutionResult(
                    call_id=call_id,
                    content=f"Not allowed to escalate to {args.target_system_id}",
                    name=self.__class__.__name__,
                    is_error=True,
                )

            if self.is_namespace(args.target_system_id):
                system_id = self.get_system_id_from_namespace_with_type(
                    args.target_system_id, SystemTypes.SYSTEM_3_CONTROL
                )
                if system_id is None:
                    return FunctionExecutionResult(
                        call_id=call_id,
                        content=f"Namespace {args.target_system_id} not found",
                        name=self.__class__.__name__,
                        is_error=True,
                    )
                else:
                    routed_target_system_id = system_id
            else:
                routed_target_system_id = args.target_system_id

            # Send the message
            return await self.send_message_to_agent(
                self.agent_id,
                HandoffMessage(
                    source=self.agent_id.key,
                    content=args.content,
                    target=routed_target_system_id,
                ),
                AgentId(self.agent_id.type, routed_target_system_id),
                cancellation_token=cancellation_token,
                span=trace.get_current_span(),
            )
        except Exception as e:
            print(f"[{self.__class__.__name__}] ERROR: {str(e)}")
            return FunctionExecutionResult(
                call_id=call_id,
                content=str(e),
                name=self.__class__.__name__,
                is_error=True,
            )
