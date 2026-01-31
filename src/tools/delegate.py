from autogen_agentchat.messages import HandoffMessage
from autogen_core import AgentId, CancellationToken
from autogen_core.models import FunctionExecutionResult
from opentelemetry import trace
from pydantic import BaseModel

from src.rbac.system_types import SystemTypes
from src.tools.rbac_base_tool import RBACBaseTool


class DelegateArgsType(BaseModel):
    target_system_id: str
    content: str


class Delegate(RBACBaseTool):
    def __init__(self, agent_id: AgentId):
        super().__init__(
            agent_id=agent_id,
            args_type=DelegateArgsType,
            tool_name=self.__class__.__name__,
            description="Delegate a task to another agent via the runtime. ",
        )

    async def run(
        self, args: DelegateArgsType, cancellation_token: CancellationToken
    ) -> FunctionExecutionResult:
        """Delegate a task to another agent via the runtime."""
        print(f"[{self.agent_id.key}/{self.tool_name}] {args}")
        call_id = self.get_call_id()
        if not self.is_action_allowed(args.target_system_id):
            print(
                f"[{self.agent_id.key}/{self.tool_name}] Not allowed to delegate to {args.target_system_id}"
            )
            return FunctionExecutionResult(
                content=f"Not allowed to delegate to {args.target_system_id}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

        resolved_target_id = self._resolve_target(args.target_system_id)
        if resolved_target_id is None:
            return FunctionExecutionResult(
                content=f"Failed to resolve target {args.target_system_id}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

        # Send the message
        return await self.send_message_to_agent(
            self.agent_id,
            HandoffMessage(
                source=self.agent_id.key,
                content=args.content,
                target=resolved_target_id,
            ),
            AgentId(self.agent_id.type, resolved_target_id),
            cancellation_token=cancellation_token,
            span=trace.get_current_span(),
        )

    def _resolve_target(self, target: str) -> str | None:
        if self.is_namespace(target):
            print(
                f"[{self.agent_id.key}/{self.tool_name}] Delegating to namespace {target}"
            )
            agent_id = self.get_system_id_from_namespace_with_type(
                target, SystemTypes.SYSTEM_3_CONTROL
            )
            if agent_id is not None:
                print(
                    f"[{self.agent_id.key}/{self.tool_name}] Delegating to {agent_id}"
                )
                return agent_id
            else:
                agent_id = self.get_system_id_from_namespace_with_type(
                    target, SystemTypes.SYSTEM_5_POLICY
                )
                if agent_id is not None:
                    print(
                        f"[{self.agent_id.key}/{self.tool_name}] Delegating to {agent_id}"
                    )
                    return agent_id
                else:
                    print(
                        f"[{self.agent_id.key}/{self.tool_name}] Failed to delegate to namespace {target}, namespace has no {SystemTypes.SYSTEM_5_POLICY}"
                    )
                    return None
        else:
            return target
