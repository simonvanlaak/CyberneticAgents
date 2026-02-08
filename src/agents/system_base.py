import logging
import os
from typing import TYPE_CHECKING, Any, List

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
from autogen_core.models import (
    ChatCompletionClient,
    LLMMessage,
    ModelCapabilities,
    ModelInfo,
    SystemMessage,
)
from autogen_core.tools import Tool, ToolSchema
from autogen_core import CancellationToken
from autogen_core.models import CreateResult, RequestUsage
from typing import Mapping, Sequence, Optional
from autogen_core.tools import BaseTool, StaticStreamWorkbench
from autogen_ext.models.openai import OpenAIChatCompletionClient
from opentelemetry import trace
from pydantic import BaseModel

from src.agents.messages import CapabilityGapMessage
from src.cyberagent.services import policies as policy_service
from src.cyberagent.services import systems as system_service
from src.cyberagent.services import teams as team_service
from src.cyberagent.secrets import get_secret
from src.enums import SystemType
from src.cyberagent.core.state import get_last_team_id, mark_team_active
from src.cyberagent.db.models.system import get_system_from_agent_id
from src.cyberagent.memory.config import (
    build_memory_registry,
    load_memory_backend_config,
)
from src.cyberagent.memory.crud import MemoryActorContext
from src.cyberagent.memory.models import MemoryScope
from src.cyberagent.memory.memengine import MemEngine
from src.cyberagent.memory.observability import (
    LoggingMemoryAuditSink,
    build_memory_metrics,
)
from src.cyberagent.memory.retrieval import (
    MemoryInjectionConfig,
    MemoryInjector,
    MemoryRetrievalService,
)
from src.cyberagent.memory.session import MemorySessionConfig, MemorySessionRecorder
from src.cyberagent.memory.reflection import MemoryReflectionService
from src.cyberagent.tools.cli_executor import (
    get_agent_skill_prompt_entries,
    get_agent_skill_tools,
)
from src.cyberagent.tools.memory_crud import MemoryCrudTool
from src.cyberagent.core.agent_naming import normalize_message_source

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


class ToolChoiceRequiredClient(ChatCompletionClient):
    def __init__(self, client: ChatCompletionClient) -> None:
        self._client = client

    @property
    def model_info(self) -> ModelInfo:
        return self._client.model_info

    async def create(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Tool | ToolSchema] = (),
        tool_choice: Tool | str = "auto",
        json_output: Optional[bool | type[BaseModel]] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[CancellationToken] = None,
    ) -> CreateResult:
        return await self._client.create(
            messages,
            tools=tools,
            tool_choice="required",
            json_output=json_output,
            extra_create_args=extra_create_args,
            cancellation_token=cancellation_token,
        )

    def create_stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Tool | ToolSchema] = (),
        tool_choice: Tool | str = "auto",
        json_output: Optional[bool | type[BaseModel]] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        return self._client.create_stream(
            messages,
            tools=tools,
            tool_choice="required",
            json_output=json_output,
            extra_create_args=extra_create_args,
            cancellation_token=cancellation_token,
        )

    async def close(self) -> None:
        await self._client.close()

    def actual_usage(self) -> RequestUsage:
        return self._client.actual_usage()

    def total_usage(self) -> RequestUsage:
        return self._client.total_usage()

    def count_tokens(
        self, messages: Sequence[LLMMessage], *, tools: Sequence[Tool | ToolSchema] = ()
    ) -> int:
        return self._client.count_tokens(messages, tools=tools)

    def remaining_tokens(
        self, messages: Sequence[LLMMessage], *, tools: Sequence[Tool | ToolSchema] = ()
    ) -> int:
        return self._client.remaining_tokens(messages, tools=tools)

    @property
    def capabilities(self) -> ModelCapabilities:  # type: ignore[override]
        return self._client.capabilities

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def _infer_system_type(agent_type: str) -> SystemType | None:
    mapping = {
        "System1": SystemType.OPERATION,
        "System2": SystemType.COORDINATION_2,
        "System3": SystemType.CONTROL,
        "System4": SystemType.INTELLIGENCE,
        "System5": SystemType.POLICY,
    }
    return mapping.get(agent_type)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _resolve_memory_scopes(
    actor: MemoryActorContext,
) -> list[tuple[MemoryScope, str]]:
    scopes = [(MemoryScope.AGENT, actor.agent_id)]
    team_namespace = os.environ.get("MEMORY_TEAM_NAMESPACE", f"team_{actor.team_id}")
    global_namespace = os.environ.get("MEMORY_GLOBAL_NAMESPACE", "user")
    if team_namespace:
        scopes.append((MemoryScope.TEAM, team_namespace))
    if global_namespace:
        scopes.append((MemoryScope.GLOBAL, global_namespace))
    return scopes


def get_model_client(
    agent_id: AgentId, structured_output: bool
) -> OpenAIChatCompletionClient:
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    if provider == "openai":
        model = os.environ.get("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        api_key = get_secret("OPENAI_API_KEY") or ""
    elif provider == "mistral":
        model = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
        base_url = os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
        api_key = get_secret("MISTRAL_API_KEY") or ""
    else:
        # Default provider is Groq for backward compatibility.
        model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
        base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        api_key = get_secret("GROQ_API_KEY") or ""

    return OpenAIChatCompletionClient(
        model=model,
        base_url=base_url,
        api_key=api_key,
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
            team_id = get_last_team_id()
            if team_id is None:
                raise RuntimeError(
                    "No teams are registered. Run 'cyberagent onboarding' to "
                    "create your first team."
                )
            self.team_id = team_id
        system_service.ensure_default_systems_for_team(self.team_id)
        mark_team_active(self.team_id)
        logger.info("Initializing %s", self.name)
        super().__init__(self.name)
        self.trace_context = trace_context or {}
        self.identity_prompt = identity_prompt
        self.responsibility_prompts = responsibility_prompts
        self._session_recorder: MemorySessionRecorder | None = None
        self.available_tools: list[BaseTool[Any, Any]] = list(
            get_agent_skill_tools(self.agent_id.__str__())
        )
        try:
            system = get_system_from_agent_id(self.agent_id.__str__())
            if system is None:
                raise ValueError("System record not found for memory_crud tool.")
            allowed, _reason = system_service.can_execute_skill(
                system.id, "memory_crud"
            )
            if allowed:
                self.available_tools.append(MemoryCrudTool(self.agent_id))
            else:
                logger.info("memory_crud tool not enabled for system_id=%s", system.id)
        except Exception as exc:
            logger.warning("Failed to initialize memory_crud tool: %s", exc)
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
        tool_choice_required: bool = False,
        include_memory_context: bool = True,
    ) -> TaskResult:
        mark_team_active(self.team_id)
        self._agent._reflect_on_tool_use = output_content_type is not None
        if output_content_type is None:
            model_client = get_model_client(self.agent_id, False)
            if tool_choice_required:
                model_client = ToolChoiceRequiredClient(model_client)
            self._agent._model_client = model_client
            self._agent._workbench = [StaticStreamWorkbench(self.tools)]
        else:
            self._agent._model_client = get_model_client(self.agent_id, True)
            self._agent._workbench = []

        # get trace context from message or use agent's stored trace context
        last_message = chat_messages[-1]
        memory_context = (
            self._build_memory_context(last_message) if include_memory_context else []
        )
        await self._set_system_prompt(message_specific_prompts, memory_context)
        self._agent._output_content_type = output_content_type
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
            except (ValueError, SyntaxError):
                message_trace_context = {}
        else:
            message_trace_context = message_trace_context_raw

        # Use message trace context if available, otherwise fall back to agent's stored context
        trace_context = (
            message_trace_context if message_trace_context else self.trace_context
        )

        # Set up proper trace context propagation using W3C format
        parent_context = None
        carrier: dict[str, str] = {}
        if trace_context and isinstance(trace_context, dict):
            if "traceparent" in trace_context and "tracestate" in trace_context:
                carrier["traceparent"] = trace_context["traceparent"]
                carrier["tracestate"] = trace_context["tracestate"]
            elif "trace_id" in trace_context and "span_id" in trace_context:
                trace_id_hex = trace_context["trace_id"]
                span_id_hex = trace_context["span_id"]
                traceparent = f"00-{trace_id_hex}-{span_id_hex}-01"
                carrier["traceparent"] = traceparent
                carrier["tracestate"] = ""

            if carrier:
                if last_message.metadata is None:
                    last_message.metadata = {}
                last_message.metadata.update(carrier)

                from opentelemetry.trace.propagation.tracecontext import (
                    TraceContextTextMapPropagator,
                )

                propagator = TraceContextTextMapPropagator()
                parent_context = propagator.extract(carrier)

        tracer = trace.get_tracer(__name__)
        if parent_context is not None:
            span_context = tracer.start_as_current_span(
                f"{self.agent_id.key}_processing",
                context=parent_context,
            )
        else:
            span_context = tracer.start_as_current_span(
                f"{self.agent_id.key}_processing"
            )

        with span_context as processing_span:
            processing_span.set_attribute("agent", str(self.agent_id))
            processing_span.set_attribute("message_type", "processing")

            # get response
            task_result: TaskResult = await self._agent.run(
                task=chat_messages, cancellation_token=ctx.cancellation_token
            )
        self._record_session_logs(chat_messages, task_result)
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

        span_context = processing_span.get_span_context()
        traceparent = (
            f"00-{format(span_context.trace_id, '032x')}-"
            f"{format(span_context.span_id, '016x')}-01"
        )
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
        memory_context: list[str] | None = None,
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
        messages.append("# MEMORY")
        messages.extend(self._memory_prompt_entries())
        if memory_context:
            messages.append("# MEMORY CONTEXT")
            messages.extend(memory_context)
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

    def _build_memory_context(self, last_message: BaseTextChatMessage) -> list[str]:
        system = get_system_from_agent_id(self.agent_id.__str__())
        if system is None:
            return []
        actor = MemoryActorContext(
            agent_id=system.agent_id_str,
            system_id=system.id,
            team_id=system.team_id,
            system_type=system.type,
        )
        query_text = last_message.to_text()
        config = load_memory_backend_config()
        registry = build_memory_registry(config)
        metrics = build_memory_metrics()
        engine = MemEngine(registry=registry, metrics=metrics)
        retrieval = MemoryRetrievalService(
            registry=registry,
            metrics=metrics,
            engine=engine,
            audit_sink=LoggingMemoryAuditSink(),
        )
        injector = MemoryInjector(
            config=MemoryInjectionConfig(
                max_chars=_env_int("MEMORY_INJECTION_MAX_CHARS", 1200),
                per_entry_max_chars=_env_int(
                    "MEMORY_INJECTION_PER_ENTRY_MAX_CHARS", 400
                ),
            ),
            metrics=metrics,
        )
        entries = []
        for scope, namespace in _resolve_memory_scopes(actor):
            try:
                result = retrieval.search_entries(
                    actor=actor,
                    scope=scope,
                    namespace=namespace,
                    query_text=query_text,
                    limit=_env_int("MEMORY_RETRIEVAL_LIMIT", 6),
                )
            except PermissionError:
                continue
            entries.extend(result.items)
        deduped = []
        seen: set[str] = set()
        for entry in entries:
            if entry.id in seen:
                continue
            seen.add(entry.id)
            deduped.append(entry)
        return injector.build_prompt_entries(deduped)

    def _record_session_logs(
        self,
        chat_messages: list[BaseTextChatMessage],
        task_result: TaskResult,
    ) -> None:
        if os.environ.get("MEMORY_SESSION_LOGGING", "true").lower() in {
            "0",
            "false",
            "no",
        }:
            return
        system = get_system_from_agent_id(self.agent_id.__str__())
        if system is None:
            return
        actor = MemoryActorContext(
            agent_id=system.agent_id_str,
            system_id=system.id,
            team_id=system.team_id,
            system_type=system.type,
        )
        user_message = chat_messages[-1].to_text() if chat_messages else ""
        response_text = ""
        if task_result.messages:
            response_text = task_result.messages[-1].to_text()
        logs = []
        if user_message:
            logs.append(f"user: {user_message}")
        if response_text:
            logs.append(f"assistant: {response_text}")
        if not logs:
            return
        recorder = self._get_session_recorder()
        recorder.record(
            actor=actor,
            scope=MemoryScope.AGENT,
            namespace=actor.agent_id,
            logs=logs,
        )

    def _get_session_recorder(self) -> MemorySessionRecorder:
        if self._session_recorder is not None:
            return self._session_recorder
        config = load_memory_backend_config()
        registry = build_memory_registry(config)
        engine = MemEngine(registry=registry)
        reflection = MemoryReflectionService(registry=registry, engine=engine)
        session_config = MemorySessionConfig(
            max_log_chars=_env_int("MEMORY_SESSION_LOG_MAX_CHARS", 2000),
            compaction_threshold_chars=_env_int(
                "MEMORY_COMPACTION_THRESHOLD_CHARS", 8000
            ),
            reflection_interval_seconds=_env_int(
                "MEMORY_REFLECTION_INTERVAL_SECONDS", 3600
            ),
            max_entries_per_namespace=_env_int(
                "MEMORY_MAX_ENTRIES_PER_NAMESPACE", 1000
            ),
        )
        self._session_recorder = MemorySessionRecorder(
            registry=registry,
            reflection_service=reflection,
            config=session_config,
        )
        return self._session_recorder

    def _memory_prompt_entries(self) -> list[str]:
        system_type = _infer_system_type(self.agent_id.type)
        entries = [
            "Use memory_crud to store durable facts, preferences, and constraints.",
            "Do not store secrets, credentials, or volatile tool output.",
            "Default scope is agent; team/global scopes require explicit namespace.",
            "Use if_match on update/delete to avoid overwriting concurrent changes.",
            "Treat cursors as opaque tokens; use list pagination as provided.",
        ]
        if system_type == SystemType.INTELLIGENCE:
            entries.append(
                "Permission override: you may read/write team and global scopes; follow namespace rules."
            )
        elif system_type in {SystemType.CONTROL, SystemType.POLICY}:
            entries.append(
                "Permission override: you may read/write team scope; do not write global."
            )
        elif system_type in {SystemType.OPERATION, SystemType.COORDINATION_2}:
            entries.append(
                "Permission override: you may read team scope but must not write team/global."
            )
        return entries

    def _was_tool_called(self, response: TaskResult | Response, tool_name: str) -> bool:
        def _iter_events() -> list[BaseAgentEvent]:
            events: list[BaseAgentEvent] = []
            if isinstance(response, TaskResult):
                for message in response.messages:
                    if isinstance(message, BaseAgentEvent):
                        events.append(message)
            else:
                for message in response.inner_messages or []:
                    if isinstance(message, BaseAgentEvent):
                        events.append(message)
            return events

        for inner_message in _iter_events():
            if isinstance(inner_message, ToolCallExecutionEvent):
                for functionExecutionResult in inner_message.content:
                    if functionExecutionResult.name == tool_name:
                        return True
        return False

    async def _publish_message_to_agent(
        self, message: BaseChatMessage, agent_id: AgentId
    ):
        if isinstance(message, BaseTextChatMessage):
            message.source = normalize_message_source(message.source)
        topic_type = f"{agent_id.type}:"
        topic_source = agent_id.key.replace("/", "_")
        logger.debug(
            "%s -> %s -> %s/%s",
            self.id.__str__(),
            message.__class__.__name__,
            agent_id.type,
            topic_source,
        )
        if isinstance(message, BaseTextChatMessage) and isinstance(
            message.content, str
        ):
            summary = message.content.replace("\n", " ")
            if len(summary) > 200:
                summary = f"{summary[:200]}..."
            detail_line = f"...[{self.id.__str__()}] message content: {summary}"
            logger.debug(detail_line)
        return await self.publish_message(
            message=message,
            topic_id=TopicId(topic_type, topic_source),
        )

    def _get_systems_by_type(self, type: SystemType) -> List["System"]:
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
            if isinstance(last_message, BaseTextChatMessage) and isinstance(
                last_message.content, str
            ):
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
