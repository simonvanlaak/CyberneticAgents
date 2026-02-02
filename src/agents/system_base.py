import logging
import os
from typing import TYPE_CHECKING, List

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import (
    BaseAgentEvent,
    BaseChatMessage,
    BaseTextChatMessage,
    HandoffMessage,
    StructuredMessage,
    TextMessage,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
    ToolCallSummaryMessage,
)
from autogen_core import (
    AgentId,
    MessageContext,
    RoutedAgent,
    TopicId,
    message_handler,
)
from autogen_core.models import ModelInfo, SystemMessage
from autogen_core.tools import StaticStreamWorkbench
from autogen_ext.models.openai import OpenAIChatCompletionClient
from opentelemetry import trace
from pydantic import BaseModel

from src.agents.messages import CapabilityGapMessage
from src.cyberagent.services import policies as policy_service
from src.cyberagent.services import systems as system_service
from src.cyberagent.services import teams as team_service
from src.cyberagent.core.state import get_or_create_last_team_id, mark_team_active
from src.cyberagent.tools.cli_executor import (
    get_agent_skill_prompt_entries,
    get_agent_skill_tools,
)

if TYPE_CHECKING:
    from src.cyberagent.db.models.system import System

SYSTEM_TYPES = {
    1: "operation",
    2: "coordination",
    3: "control",
    4: "intelligence",
    5: "policy",
    6: "user",
}
logger = logging.getLogger(__name__)


def get_model_client(
    agent_id: AgentId, structured_output: bool
) -> OpenAIChatCompletionClient:
    # In the future, each system could have a specific model and provider defined, including temperatures etc.
    return OpenAIChatCompletionClient(
        # model="llama-3.1-8b-instant",
        model="openai/gpt-oss-20b",
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ.get("GROQ_API_KEY", ""),
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=False,
            family="unknown",
            structured_output=structured_output,
        ),
    )


class SystemBase(RoutedAgent):
    def __init__(
        self,
        name: str,
        identity_prompt: str,
        responsibility_prompts: List[str],
        trace_context: dict | None = None,
    ):
        if "/" not in name:
            name = f"{self.__class__.__name__}/{name}"
        self.name = name.replace("/", "_")
        self.agent_id = AgentId.from_str(name)
        team_id_env = os.environ.get("CYBERAGENT_ACTIVE_TEAM_ID")
        if team_id_env:
            try:
                team_id = int(team_id_env)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid CYBERAGENT_ACTIVE_TEAM_ID '{team_id_env}'."
                ) from exc
            if team_service.get_team(team_id) is None:
                raise ValueError(f"Team id {team_id} is not registered.")
            self.team_id = team_id
        else:
            self.team_id = get_or_create_last_team_id()
        system_service.ensure_default_systems_for_team(self.team_id)
        mark_team_active(self.team_id)
        logger.info("Initializing %s", self.name)
        super().__init__(self.name)
        self.trace_context = trace_context or {}
        self.identity_prompt = identity_prompt
        self.responsibility_prompts = responsibility_prompts
        self.available_tools = get_agent_skill_tools(self.agent_id.__str__())
        self.tools = self.available_tools
        # Create a valid Python identifier for the AssistantAgent
        # Replace slashes with underscores for the agent name
        self._agent = AssistantAgent(
            name=self.name,
            system_message=f"You are '{self.name}' a helpful assistant.",
            model_client=get_model_client(self.agent_id, False),
            tools=self.tools,
            reflect_on_tool_use=True,
            model_client_stream=False,
            max_tool_iterations=5,
        )

    async def run(
        self,
        chat_messages: List[BaseTextChatMessage],
        ctx: MessageContext,
        message_specific_prompts: List[str] = [],
        output_content_type: type[BaseModel] | None = None,
    ) -> TaskResult:
        mark_team_active(self.team_id)
        self._agent._reflect_on_tool_use = output_content_type is not None
        if output_content_type is None:
            self._agent._model_client = get_model_client(self.agent_id, False)
            self._agent._workbench = [StaticStreamWorkbench(self.tools)]
        else:
            self._agent._model_client = get_model_client(self.agent_id, True)
            self._agent._workbench = []

        await self._set_system_prompt(message_specific_prompts)
        self._agent._output_content_type = output_content_type
        # get trace context from message or use agent's stored trace context
        last_message = chat_messages[-1]
        message_trace_context_raw = (
            last_message.metadata.get("trace_context", {})
            if last_message.metadata
            else {}
        )

        # Convert from string to dict if needed
        if isinstance(message_trace_context_raw, str):
            try:
                import ast

                message_trace_context = ast.literal_eval(message_trace_context_raw)
            except:
                message_trace_context = {}
        else:
            message_trace_context = message_trace_context_raw

        # Use message trace context if available, otherwise fall back to agent's stored context
        trace_context = (
            message_trace_context if message_trace_context else self.trace_context
        )

        # Set up proper trace context propagation using W3C format
        if trace_context and isinstance(trace_context, dict):
            # Convert our trace context to proper W3C format if needed
            carrier = {}
            if "traceparent" in trace_context and "tracestate" in trace_context:
                # Already in proper format, use directly
                carrier["traceparent"] = trace_context["traceparent"]
                carrier["tracestate"] = trace_context["tracestate"]
            elif "trace_id" in trace_context and "span_id" in trace_context:
                # Convert from our custom format to W3C traceparent format
                # traceparent format: version-flag-trace_id-span_id
                trace_id_hex = trace_context["trace_id"]
                span_id_hex = trace_context["span_id"]
                traceparent = f"00-{trace_id_hex}-{span_id_hex}-01"
                carrier["traceparent"] = traceparent
                carrier["tracestate"] = ""  # Empty tracestate for now

            # Set the carrier in the message metadata for proper propagation
            if last_message.metadata is None:
                last_message.metadata = {}
            last_message.metadata.update(carrier)

            # Create a new span with the parent context for proper trace continuity
            from opentelemetry.trace.propagation.tracecontext import (
                TraceContextTextMapPropagator,
            )

            propagator = TraceContextTextMapPropagator()

            # Extract the parent context from the carrier
            parent_context = propagator.extract(carrier)

            # Create a new span with the parent context
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(
                f"{self.agent_id.key}_processing",
                context=parent_context,
            ) as processing_span:
                processing_span.set_attribute("agent", str(self.agent_id))
                processing_span.set_attribute("message_type", "processing")

        # get response
        task_result: TaskResult = await self._agent.run(
            task=chat_messages, cancellation_token=ctx.cancellation_token
        )
        for message in task_result.messages:
            if isinstance(message, ToolCallRequestEvent):
                for func_call in message.content:
                    log_line = (
                        f"...[{self.agent_id.__str__()}] use tool {func_call.name}"
                    )
                    logger.debug(log_line)
            elif isinstance(message, ToolCallExecutionEvent):
                for func_result in message.content:
                    log_line = f"...[{func_result.name}]: {func_result.content}"
                    logger.debug(log_line)
            else:
                log_line = (
                    f"...[{self.agent_id.__str__()}]: {message.__class__.__name__} - "
                    f"{message.to_text()[:50]}"
                )
                logger.debug(log_line)
        # attach trace context to response using proper W3C format
        if task_result.messages[-1].metadata is None:
            task_result.messages[-1].metadata = {}

        # Get current span context to propagate
        current_span = trace.get_current_span()
        if current_span:
            # Create proper traceparent format for response
            span_context = current_span.get_span_context()
            traceparent = f"00-{format(span_context.trace_id, '032x')}-{format(span_context.span_id, '016x')}-01"
            task_result.messages[-1].metadata["traceparent"] = traceparent
            task_result.messages[-1].metadata["tracestate"] = ""

        return task_result

    @message_handler
    async def handle_tool_call_summary(
        self,
        message: ToolCallSummaryMessage,
        ctx: MessageContext,
    ) -> TextMessage:
        logger.debug(
            "[%s] Received tool call summary: %s", self.agent_id.key, message.content
        )

        response = await self.run([message], ctx)
        text_message = self._get_structured_message(response, TextMessage)
        logger.debug(
            "[%s] Response completed: %s", self.agent_id.key, text_message.content
        )
        return text_message

    @message_handler
    async def handle_handoff(
        self,
        message: HandoffMessage,
        ctx: MessageContext,
    ) -> TextMessage:
        logger.debug(
            "[%s] Received handoff message: %s", self.agent_id.key, message.content
        )

        response = await self.run([message], ctx)
        text_message = self._get_structured_message(response, TextMessage)

        logger.debug(
            "[%s] Handoff message completed: %s",
            self.agent_id.key,
            text_message.content,
        )
        return text_message

    async def capability_gap_tool(self, task_id: int, content: str):
        # For now, we'll need to fetch the task from the database
        # This is a temporary fix - in production, we should pass the assignee directly
        from src.cyberagent.services import tasks as task_service

        task = task_service.get_task_by_id(task_id)
        if task.assignee is None:
            raise ValueError("Task assignee cannot be None")
        return await self._publish_message_to_agent(
            CapabilityGapMessage(
                task_id=task_id,
                assignee_agent_id_str=task.assignee,
                content=content,
                source=self.id.key,
            ),
            AgentId.from_str(task.assignee),
        )

    async def _set_system_prompt(
        self,
        message_specific_prompts: List[str] = [],
    ):
        messages = []
        messages.append("# IDENTITY")
        messages.append(self.identity_prompt)
        messages.append("# RESPONSIBILITIES")
        messages.append("# TEAM POLICIES")
        messages.append(
            "You are part of a team of systems working together to achieve a common goal, you must adhere to the following policies:"
        )
        messages.extend(policy_service.get_team_policy_prompts(self.agent_id.__str__()))
        messages.append("# INDIVIDUAL POLICIES")
        messages.append("You must adhere at all times to the following policies:")
        messages.extend(
            policy_service.get_system_policy_prompts(self.agent_id.__str__())
        )
        messages.append("# RESPONSIBILITIES")
        messages.extend(self.responsibility_prompts)
        messages.append("# SKILLS")
        skill_entries = get_agent_skill_prompt_entries(self.agent_id.__str__())
        if skill_entries:
            messages.extend(skill_entries)
        else:
            messages.append("No skills available")
        messages.append("# TOOLS")
        if len(self._agent._workbench) > 0:
            for workbench in self._agent._workbench:
                for tool in await workbench.list_tools():
                    messages.append(f"{tool.get('name')}: {tool.get('description')}")
        else:
            messages.append("No tools available")
        if len(message_specific_prompts) > 0:
            messages.append("# MESSAGE SPECIFIC PROMPTS")
            messages.extend(message_specific_prompts)

        self._agent._system_messages = [
            SystemMessage(content=message) for message in messages
        ]

    def _was_tool_called(self, response: Response, tool_name: str) -> bool:
        # TODO change this to task result
        if response.inner_messages:
            for inner_message in response.inner_messages:
                if isinstance(inner_message, ToolCallExecutionEvent):
                    for functionExecutionResult in inner_message.content:
                        if functionExecutionResult.name == tool_name:
                            return True
        return False

    async def _publish_message_to_agent(
        self, message: BaseChatMessage, agent_id: AgentId
    ):
        topic_type = f"{agent_id.type}:"
        topic_source = agent_id.key.replace("/", "_")
        logger.debug(
            "%s -> %s -> %s/%s",
            self.id.__str__(),
            message.__class__.__name__,
            agent_id.type,
            topic_source,
        )
        if hasattr(message, "content") and isinstance(message.content, str):
            summary = message.content.replace("\n", " ")
            if len(summary) > 200:
                summary = f"{summary[:200]}..."
            detail_line = f"...[{self.id.__str__()}] message content: {summary}"
            logger.debug(detail_line)
        return await self.publish_message(
            message=message,
            topic_id=TopicId(topic_type, topic_source),
        )

    def _get_systems_by_type(self, type: int) -> List["System"]:
        if not self.team_id:
            raise ValueError("Team id is not set for this agent.")
        return system_service.get_systems_by_type(self.team_id, type)

    def _get_last_message(self, result: TaskResult) -> BaseChatMessage:
        if not result.messages:
            raise ValueError("No chat message received")
        if len(result.messages) == 0:
            raise ValueError("No chat message received")
        last_event: BaseAgentEvent | None = None
        for message in reversed(result.messages):
            if isinstance(message, BaseChatMessage):
                return message
            else:
                if last_event is None:
                    last_event = message

        if last_event:
            return BaseTextChatMessage(
                source=last_event.source, content=last_event.to_text()
            )
        else:
            raise ValueError("No chat message received")

    def _get_structured_message(self, result: TaskResult, expected_type: type):
        """Extract structured response with proper error handling."""
        if not result.messages:
            raise ValueError("No chat message received")

        structured_message = None
        for message in reversed(result.messages):
            if isinstance(message, StructuredMessage):
                structured_message = message
                break

        if structured_message is None:
            last_message = self._get_last_message(result)
            if isinstance(last_message.content, str):
                try:
                    return expected_type.model_validate_json(last_message.content)
                except Exception as e:
                    raise ValueError(f"Failed to parse response: {str(e)}")
            raise ValueError("No StructuredMessage found in task result")

        if isinstance(structured_message.content, expected_type):
            return structured_message.content
        try:
            if isinstance(structured_message.content, str):
                return expected_type.model_validate_json(structured_message.content)
            raise ValueError(
                f"Expected {expected_type.__name__}, got {type(structured_message.content)}"
            )
        except Exception as e:
            raise ValueError(f"Failed to parse response: {str(e)}")
