import uuid
from typing import Any, Type

from autogen_agentchat.messages import TextMessage
from autogen_core import AgentId, CancellationToken
from autogen_core.models import FunctionExecutionResult
from autogen_core.tools import BaseTool
from opentelemetry import trace
from opentelemetry.trace import Span
from opentelemetry.context import Context
from pydantic import BaseModel

from src.rbac.enforcer import (
    check_permission,
    create_user,
    delete_system_id,
    get_allowed_actions,
    get_system_id_from_namespace_with_type,
    give_user_tool_permission,
    is_namespace,
)
from src.rbac.system_types import SystemTypes
from src.runtime import get_runtime


class RBACBaseArgsType(BaseModel):
    action: str


class RBACBaseTool(BaseTool):
    agent_id: AgentId
    tool_name: str

    def __init__(
        self,
        tool_name: str,
        description: str,
        agent_id: AgentId,
        args_type: Type[BaseModel] = RBACBaseArgsType,
    ):
        # print(f"Initializing {tool_name} with AgentId({agent_id.type}, {agent_id.key})")
        self.agent_id = agent_id
        self.namespace = self.get_namespace(agent_id.key)
        self.system_type = self.get_type(agent_id.key)
        self.tool_name = tool_name
        self.allowed_actions = self.get_allowed_actions()
        if self.allowed_actions:
            description += "\nPossible actions: " + ", ".join(self.allowed_actions)
        else:
            raise ValueError("No delegation targets available.")
        super().__init__(
            name=tool_name,
            description=description,
            return_type=FunctionExecutionResult,
            args_type=args_type,
        )

    def get_namespace(self, agent_id: str) -> str:
        if agent_id.count("_") != 2:
            raise ValueError("Invalid agent_id format")
        return agent_id.split("_")[0]

    def get_type(self, agent_id: str) -> str:
        if agent_id.count("_") != 2:
            raise ValueError("Invalid agent_id format")
        return agent_id.split("_")[1]

    def get_call_id(self) -> str:
        return f"{self.name}_{uuid.uuid4().hex}"

    def get_allowed_actions(self):
        return get_allowed_actions(self.agent_id.key, self.tool_name)

    def is_action_allowed(self, action_name: str):
        return check_permission(self.agent_id.key, self.tool_name, action_name)

    def is_namespace(self, parameter: str):
        return is_namespace(parameter)

    def get_system_id_from_namespace_with_type(
        self, namespace: str, system_type: str
    ) -> str | None:
        return get_system_id_from_namespace_with_type(namespace, system_type)

    def delete_system(self, system_id: str):
        return delete_system_id(system_id)

    def add_child_namespace(self, parent_namespace: str, child_namespace: str):
        return create_user(SystemTypes.SYSTEM_1_OPERATIONS, child_namespace)

    def give_system_id_tool_permission(
        self, system_id: str, tool_name: str, parameter: str
    ):
        return give_user_tool_permission(system_id, tool_name, parameter)

    async def send_message_to_agent(
        self,
        sender_id: AgentId,
        message: Any,
        target_id: AgentId,
        cancellation_token: CancellationToken,
        span: Span,
    ) -> FunctionExecutionResult:
        """Send a message to an agent, creating it if necessary."""
        call_id = uuid.uuid4().hex
        try:
            # continue trace
            trace_context = {}
            if span:
                span_context = span.get_span_context()
                trace_context = {
                    "trace_id": format(span_context.trace_id, "032x"),
                    "span_id": format(span_context.span_id, "016x"),
                    "is_remote": str(span_context.is_remote),
                    "trace_flags": str(span_context.trace_flags),
                }

                # Create a new span with the current span as parent for proper trace continuity
                tracer = trace.get_tracer(__name__)
                # Use the current context which already contains the parent span
                with tracer.start_as_current_span(
                    f"{self.agent_id.key}->{target_id.key}",
                ) as child_span:
                    # Set span attributes for better trace analysis
                    child_span.set_attribute("sender", self.agent_id.key)
                    child_span.set_attribute("target", target_id.key)
                    child_span.set_attribute("tool", self.tool_name)

                    # Pass the trace context in message metadata
                    if message.metadata is None:
                        message.metadata = {}
                    message.metadata["trace_context"] = str(trace_context)

                    runtime = get_runtime()
                    if target_id.type not in runtime._agent_factories:
                        raise ValueError(
                            f"Agent type {target_id.type} is not registered in runtime."
                        )
                    response_message: TextMessage = await runtime.send_message(
                        message,
                        recipient=target_id,
                        sender=sender_id,
                        cancellation_token=cancellation_token,
                    )
                    return FunctionExecutionResult(
                        call_id=call_id,
                        content=response_message.content,
                        name="send_message_to_agent",
                        is_error=False,
                    )
        except Exception as e:
            return FunctionExecutionResult(
                call_id=call_id,
                content=f"Error sending message: {e}",
                name="send_message_to_agent",
                is_error=True,
            )
