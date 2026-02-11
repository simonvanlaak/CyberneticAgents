import logging
import os
from typing import Any, List
from unittest.mock import AsyncMock

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import (
    BaseTextChatMessage,
    HandoffMessage,
    TextMessage,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
    ToolCallSummaryMessage,
)
from autogen_core import AgentId, MessageContext, RoutedAgent, message_handler
from autogen_core.models import ModelInfo, SystemMessage
from autogen_core.tools import BaseTool
from autogen_ext.models.openai import OpenAIChatCompletionClient
from opentelemetry import trace
from pydantic import BaseModel

from src.agents.messages import CapabilityGapMessage
from src.agents.system_base_mixin import SystemBaseMixin
from src.agents.tool_choice_required_client import ToolChoiceRequiredClient
from src.cyberagent.core.state import get_last_team_id, mark_team_active
from src.cyberagent.db.models.system import get_system_from_agent_id
from src.cyberagent.secrets import get_secret
from src.cyberagent.services import systems as system_service
from src.cyberagent.services import teams as team_service
from src.cyberagent.tools.cli_executor import get_agent_skill_tools
from src.cyberagent.tools.memory_crud import MemoryCrudTool
from src.cyberagent.tools.task_search import TaskSearchTool

logger = logging.getLogger(__name__)


class InternalErrorRoutedError(RuntimeError):
    """Raised after an internal error has already been routed to System5."""


def get_model_client(
    agent_id: AgentId,
    structured_output: bool,
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


class SystemBase(SystemBaseMixin, RoutedAgent):
    MESSAGE_LENGTH_ERROR_FRAGMENT = (
        "please reduce the length of the messages or completion"
    )
    TOOL_CHOICE_REQUIRED_FRAGMENT = "tool choice is required"
    TOOL_NOT_CALLED_FRAGMENT = "did not call a tool"

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
        self._session_recorder = None
        self._last_system_messages: list[SystemMessage] = []
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
            task_search_allowed, _reason = system_service.can_execute_skill(
                system.id, "task_search"
            )
            if task_search_allowed:
                self.available_tools.append(TaskSearchTool(self.agent_id))
            else:
                logger.info("task_search tool not enabled for system_id=%s", system.id)
        except Exception as exc:
            logger.warning("Failed to initialize system tools: %s", exc)
        self.tools = self.available_tools
        self._agent = self._build_assistant_agent(
            system_message=f"You are '{self.name}' a helpful assistant.",
            output_content_type=None,
            tool_choice_required=False,
            enable_tools=True,
        )

    def _build_assistant_agent(
        self,
        system_message: str,
        output_content_type: type[BaseModel] | None,
        tool_choice_required: bool,
        enable_tools: bool,
    ) -> AssistantAgent:
        model_client = get_model_client(self.agent_id, output_content_type is not None)
        if output_content_type is None and tool_choice_required:
            model_client = ToolChoiceRequiredClient(model_client)
        return AssistantAgent(
            name=self.name,
            system_message=system_message,
            model_client=model_client,
            tools=self.tools if enable_tools else [],
            reflect_on_tool_use=output_content_type is not None,
            model_client_stream=False,
            max_tool_iterations=5,
            output_content_type=output_content_type,
        )

    async def run(
        self,
        chat_messages: List[BaseTextChatMessage],
        ctx: MessageContext,
        message_specific_prompts: List[str] = [],
        output_content_type: type[BaseModel] | None = None,
        tool_choice_required: bool = False,
        include_memory_context: bool = True,
        enable_tools: bool | None = None,
    ) -> TaskResult:
        mark_team_active(self.team_id)
        prompts = list(message_specific_prompts)
        if output_content_type is not None:
            prompts.extend(self._build_output_contract_prompts(output_content_type))

        tools_enabled = (
            output_content_type is None if enable_tools is None else enable_tools
        )

        last_message = chat_messages[-1]
        memory_context = (
            self._build_memory_context(last_message) if include_memory_context else []
        )
        tools_for_prompt = self.tools if tools_enabled else []
        setattr(self, "_active_prompt_tools_override", tools_for_prompt)
        try:
            prompt_result = await self._set_system_prompt(prompts, memory_context)
        finally:
            if hasattr(self, "_active_prompt_tools_override"):
                delattr(self, "_active_prompt_tools_override")
        system_message = (
            prompt_result
            if isinstance(prompt_result, str)
            else "\n".join(msg.content for msg in self._last_system_messages)
        )
        if isinstance(getattr(self._agent, "run", None), AsyncMock):
            setattr(
                self._agent, "_reflect_on_tool_use", output_content_type is not None
            )
            if tool_choice_required and output_content_type is None:
                model_client = get_model_client(self.agent_id, False)
                setattr(
                    self._agent, "_model_client", ToolChoiceRequiredClient(model_client)
                )
        else:
            self._agent = self._build_assistant_agent(
                system_message=system_message,
                output_content_type=output_content_type,
                tool_choice_required=tool_choice_required,
                enable_tools=tools_enabled,
            )

        message_trace_context_raw = (
            last_message.metadata.get("trace_context", {})
            if last_message.metadata
            else {}
        )
        if isinstance(message_trace_context_raw, str):
            try:
                import ast

                message_trace_context = ast.literal_eval(message_trace_context_raw)
            except (ValueError, SyntaxError):
                message_trace_context = {}
        else:
            message_trace_context = message_trace_context_raw

        trace_context = (
            message_trace_context if message_trace_context else self.trace_context
        )

        parent_context = None
        carrier: dict[str, str] = {}
        if trace_context and isinstance(trace_context, dict):
            if "traceparent" in trace_context and "tracestate" in trace_context:
                carrier["traceparent"] = trace_context["traceparent"]
                carrier["tracestate"] = trace_context["tracestate"]
            elif "trace_id" in trace_context and "span_id" in trace_context:
                traceparent = (
                    f"00-{trace_context['trace_id']}-{trace_context['span_id']}-01"
                )
                carrier["traceparent"] = traceparent
                carrier["tracestate"] = ""
            if carrier:
                if last_message.metadata is None:
                    last_message.metadata = {}
                last_message.metadata.update(carrier)
                from opentelemetry.trace.propagation.tracecontext import (
                    TraceContextTextMapPropagator,
                )

                parent_context = TraceContextTextMapPropagator().extract(carrier)

        tracer = trace.get_tracer(__name__)
        span_context = (
            tracer.start_as_current_span(
                f"{self.agent_id.key}_processing",
                context=parent_context,
            )
            if parent_context is not None
            else tracer.start_as_current_span(f"{self.agent_id.key}_processing")
        )

        with span_context as processing_span:
            processing_span.set_attribute("agent", str(self.agent_id))
            processing_span.set_attribute("message_type", "processing")
            try:
                task_result: TaskResult = await self._agent.run(
                    task=chat_messages,
                    cancellation_token=ctx.cancellation_token,
                )
            except Exception as exc:
                retry_result: TaskResult | None = None

                provider_error_summary = None
                try:
                    from src.agents.provider_errors import (
                        extract_provider_error_details,
                    )

                    details = extract_provider_error_details(exc)
                    if details is not None and details.status_code is not None:
                        provider_error_summary = (
                            "provider_http_error"
                            f" status={details.status_code}"
                            f" request_id={details.request_id or 'unknown'}"
                            f" type={details.error_type or 'unknown'}"
                            f" code={details.error_code or 'unknown'}"
                            f" message={details.message or details.raw_body_excerpt or 'n/a'}"
                        )
                        logger.warning(
                            "Provider HTTP error for %s: %s",
                            self.agent_id.__str__(),
                            provider_error_summary,
                        )
                except Exception:
                    provider_error_summary = None
                if self._is_message_length_error(exc):
                    retry_result = await self._retry_with_compacted_message_payload(
                        chat_messages=chat_messages,
                        ctx=ctx,
                        prompts=prompts,
                        output_content_type=output_content_type,
                        tool_choice_required=tool_choice_required,
                        tools_enabled=tools_enabled,
                    )
                elif self._is_tool_arguments_json_error(exc):
                    logger.warning(
                        "Tool call arguments JSON parse failed for %s. Retrying once.",
                        self.agent_id.__str__(),
                    )
                    tool_retry_messages: list[BaseTextChatMessage] = [
                        *chat_messages,
                        TextMessage(
                            source=self.name,
                            content=self._build_tool_arguments_retry_instruction(),
                        ),
                    ]
                    retry_result = await self._agent.run(
                        task=tool_retry_messages,
                        cancellation_token=ctx.cancellation_token,
                    )
                elif self._is_tool_call_name_validation_error(exc):
                    logger.warning(
                        "Tool call name validation failed for %s. Retrying once with normalized tool naming instruction.",
                        self.agent_id.__str__(),
                    )
                    tool_name_retry_messages: list[BaseTextChatMessage] = [
                        *chat_messages,
                        TextMessage(
                            source=self.name,
                            content=self._build_tool_call_name_retry_instruction(),
                        ),
                    ]
                    retry_result = await self._agent.run(
                        task=tool_name_retry_messages,
                        cancellation_token=ctx.cancellation_token,
                    )
                if retry_result is not None:
                    task_result = retry_result
                elif self._is_required_tool_choice_missing_call_error(
                    exc=exc,
                    output_content_type=output_content_type,
                ):
                    raise
                elif (
                    output_content_type is None
                    or not self._is_json_generation_failure(exc)
                ):
                    if self.agent_id.type == "System5":
                        raise
                    await self._route_internal_error_to_policy_system(
                        failed_message_type=chat_messages[-1].__class__.__name__,
                        error_summary=(
                            f"{str(exc)} | {provider_error_summary}"
                            if provider_error_summary
                            else str(exc)
                        ),
                        task_id=getattr(chat_messages[-1], "task_id", None),
                    )
                    raise InternalErrorRoutedError("internal_error_routed") from exc
                else:
                    logger.warning(
                        "Structured generation failed for %s. Falling back to unstructured retry.",
                        output_content_type.__name__,
                    )
                    fallback_messages: list[BaseTextChatMessage] = [
                        *chat_messages,
                        TextMessage(
                            source=self.name,
                            content=self._build_output_fallback_instruction(
                                output_content_type
                            ),
                        ),
                    ]
                    if not isinstance(getattr(self._agent, "run", None), AsyncMock):
                        self._agent = self._build_assistant_agent(
                            system_message=system_message,
                            output_content_type=None,
                            tool_choice_required=False,
                            enable_tools=False,
                        )
                    task_result = await self._agent.run(
                        task=fallback_messages,
                        cancellation_token=ctx.cancellation_token,
                    )

            if output_content_type is not None:
                parse_error = self._get_structured_parse_error(
                    task_result,
                    output_content_type,
                )
                if parse_error is not None:
                    logger.warning(
                        "Structured output parse failed for %s. Retrying once.",
                        output_content_type.__name__,
                    )
                    retry_messages: list[BaseTextChatMessage] = [
                        *chat_messages,
                        TextMessage(
                            source=self.name,
                            content=self._build_output_retry_instruction(
                                output_content_type
                            ),
                        ),
                    ]
                    task_result = await self._agent.run(
                        task=retry_messages,
                        cancellation_token=ctx.cancellation_token,
                    )

        self._record_session_logs(chat_messages, task_result)
        for message in task_result.messages:
            if isinstance(message, ToolCallRequestEvent):
                for func_call in message.content:
                    logger.debug(
                        "...[%s] use tool %s", self.agent_id.__str__(), func_call.name
                    )
            elif isinstance(message, ToolCallExecutionEvent):
                for func_result in message.content:
                    logger.debug("...[%s]: %s", func_result.name, func_result.content)

        if task_result.messages[-1].metadata is None:
            task_result.messages[-1].metadata = {}
        span_info = processing_span.get_span_context()
        traceparent = (
            f"00-{format(span_info.trace_id, '032x')}-"
            f"{format(span_info.span_id, '016x')}-01"
        )
        task_result.messages[-1].metadata["traceparent"] = traceparent
        task_result.messages[-1].metadata["tracestate"] = ""
        return task_result

    def _is_message_length_error(self, exc: Exception) -> bool:
        return self.MESSAGE_LENGTH_ERROR_FRAGMENT in str(exc).lower()

    def _is_required_tool_choice_missing_call_error(
        self,
        exc: Exception,
        output_content_type: type[BaseModel] | None,
    ) -> bool:
        if output_content_type is not None:
            return False
        error_text = str(exc).lower()
        return (
            self.TOOL_CHOICE_REQUIRED_FRAGMENT in error_text
            and self.TOOL_NOT_CALLED_FRAGMENT in error_text
        )

    async def _retry_with_compacted_message_payload(
        self,
        chat_messages: List[BaseTextChatMessage],
        ctx: MessageContext,
        prompts: List[str],
        output_content_type: type[BaseModel] | None,
        tool_choice_required: bool,
        tools_enabled: bool,
    ) -> TaskResult | None:
        logger.warning(
            "Message length exceeded provider limit for %s. Retrying with compacted context.",
            self.agent_id.__str__(),
        )
        compacted_messages = self._compact_chat_messages_for_retry(chat_messages)
        tools_for_prompt = self.tools if tools_enabled else []
        setattr(self, "_active_prompt_tools_override", tools_for_prompt)
        try:
            prompt_result = await self._set_system_prompt(prompts, [])
        finally:
            if hasattr(self, "_active_prompt_tools_override"):
                delattr(self, "_active_prompt_tools_override")
        compacted_system_message = (
            prompt_result
            if isinstance(prompt_result, str)
            else "\n".join(msg.content for msg in self._last_system_messages)
        )
        if not isinstance(getattr(self._agent, "run", None), AsyncMock):
            self._agent = self._build_assistant_agent(
                system_message=compacted_system_message,
                output_content_type=output_content_type,
                tool_choice_required=tool_choice_required,
                enable_tools=tools_enabled,
            )
        return await self._agent.run(
            task=compacted_messages,
            cancellation_token=ctx.cancellation_token,
        )

    def _compact_chat_messages_for_retry(
        self,
        chat_messages: List[BaseTextChatMessage],
    ) -> List[BaseTextChatMessage]:
        max_chars = int(os.environ.get("SYSTEM_CHAT_MESSAGE_MAX_CHARS", "4000"))
        if max_chars <= 0:
            return chat_messages
        compacted: list[BaseTextChatMessage] = []
        for message in chat_messages:
            content = getattr(message, "content", None)
            if not isinstance(content, str) or len(content) <= max_chars:
                compacted.append(message)
                continue
            truncated_content = self._truncate_chat_message_content(content, max_chars)
            if hasattr(message, "model_copy"):
                copied = message.model_copy(deep=True)
                setattr(copied, "content", truncated_content)
                compacted.append(copied)
                continue
            compacted.append(message)
        return compacted

    def _truncate_chat_message_content(self, content: str, max_chars: int) -> str:
        if len(content) <= max_chars:
            return content
        suffix = "\n...[truncated for message budget]"
        if max_chars <= len(suffix):
            return content[:max_chars]
        return f"{content[: max_chars - len(suffix)]}{suffix}"

    @message_handler
    async def handle_tool_call_summary(
        self,
        message: ToolCallSummaryMessage,
        ctx: MessageContext,
    ) -> TextMessage:
        response = await self.run([message], ctx)
        return self._get_structured_message(response, TextMessage)

    @message_handler
    async def handle_handoff(
        self,
        message: HandoffMessage,
        ctx: MessageContext,
    ) -> TextMessage:
        response = await self.run([message], ctx)
        return self._get_structured_message(response, TextMessage)

    async def capability_gap_tool(self, task_id: int, content: str):
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
