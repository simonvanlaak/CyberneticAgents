import json
import logging
import os
import sqlite3
from typing import TYPE_CHECKING, Any, List

from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import (
    BaseAgentEvent,
    BaseChatMessage,
    BaseTextChatMessage,
    StructuredMessage,
    ToolCallExecutionEvent,
)
from autogen_core import AgentId, TopicId
from autogen_core.models import SystemMessage
from pydantic import BaseModel

from src.agents.messages import InternalErrorMessage, InvalidReviewRecoveryContract
from src.cyberagent.core.agent_naming import normalize_message_source
from src.cyberagent.db.models.system import get_system_from_agent_id
from src.cyberagent.memory.config import (
    build_memory_registry,
    load_memory_backend_config,
)
from src.cyberagent.memory.crud import MemoryActorContext
from src.cyberagent.memory.memengine import MemEngine
from src.cyberagent.memory.models import MemoryScope
from src.cyberagent.memory.observability import (
    LoggingMemoryAuditSink,
    build_memory_metrics,
)
from src.cyberagent.memory.reflection import MemoryReflectionService
from src.cyberagent.memory.retrieval import (
    MemoryInjectionConfig,
    MemoryInjector,
    MemoryRetrievalService,
)
from src.cyberagent.memory.session import MemorySessionConfig, MemorySessionRecorder
from src.cyberagent.services import policies as policy_service
from src.cyberagent.services import systems as system_service
from src.cyberagent.tools.cli_executor import get_agent_skill_prompt_entries
from src.enums import SystemType

if TYPE_CHECKING:
    from src.cyberagent.db.models.system import System

logger = logging.getLogger(__name__)


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


def _resolve_memory_scopes(actor: MemoryActorContext) -> list[tuple[MemoryScope, str]]:
    scopes = [(MemoryScope.AGENT, actor.agent_id)]
    team_namespace = os.environ.get("MEMORY_TEAM_NAMESPACE", f"team_{actor.team_id}")
    global_namespace = os.environ.get("MEMORY_GLOBAL_NAMESPACE", "user")
    if team_namespace:
        scopes.append((MemoryScope.TEAM, team_namespace))
    if global_namespace:
        scopes.append((MemoryScope.GLOBAL, global_namespace))
    return scopes


class SystemBaseMixin:
    MESSAGE_BUDGET_TRUNCATION_NOTE = "[Prompt compacted for provider message budget]"
    agent_id: AgentId
    team_id: int
    name: str
    identity_prompt: str
    responsibility_prompts: list[str]
    tools: list[Any]
    _agent: Any
    _last_system_messages: list[SystemMessage]
    _session_recorder: MemorySessionRecorder | None
    publish_message: Any

    if TYPE_CHECKING:

        @property
        def id(self) -> AgentId: ...

    def _build_output_contract_prompts(
        self,
        output_content_type: type[BaseModel],
    ) -> list[str]:
        schema = json.dumps(output_content_type.model_json_schema(), ensure_ascii=True)
        return [
            "# OUTPUT CONTRACT",
            f"Expected response type: {output_content_type.__name__}",
            "Return strict JSON only. Do not include prose, markdown, or explanations.",
            "The JSON response must match this schema exactly:",
            schema,
        ]

    def _build_output_retry_instruction(
        self,
        output_content_type: type[BaseModel],
    ) -> str:
        schema = json.dumps(output_content_type.model_json_schema(), ensure_ascii=True)
        return (
            "Return strict JSON only with no prose or markdown. "
            f"Your output must match the {output_content_type.__name__} schema exactly: "
            f"{schema}"
        )

    def _build_output_fallback_instruction(
        self,
        output_content_type: type[BaseModel],
    ) -> str:
        schema = json.dumps(output_content_type.model_json_schema(), ensure_ascii=True)
        return (
            "JSON generation failed in structured mode. "
            "Return strict JSON only with this schema: "
            f"{schema}. "
            "Do not include markdown or prose outside the JSON object."
        )

    def _get_structured_parse_error(
        self,
        result: TaskResult,
        output_content_type: type[BaseModel],
    ) -> str | None:
        try:
            self._get_structured_message(result, output_content_type)
            return None
        except ValueError as exc:
            return str(exc)

    def _is_json_generation_failure(self, exc: Exception) -> bool:
        text = str(exc).lower()
        return "json_validate_failed" in text or "failed to generate json" in text

    def _is_non_strict_tool_parse_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        return (
            "only `strict` function tools can be auto-parsed" in text
            or "default arguments are not allowed in strict mode" in text
        )

    def _is_tool_arguments_json_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        return (
            "tool_use_failed" in text
            and "failed to parse tool call arguments as json" in text
        )

    def _build_tool_arguments_retry_instruction(self) -> str:
        return (
            "Retry the previous response. If you call a tool, the arguments must be "
            "strict valid JSON with properly balanced quotes/braces, no trailing "
            "characters, and no markdown."
        )

    def _is_tool_call_name_validation_error(self, exc: Exception) -> bool:
        """Detect provider tool-name validation failures.

        Some providers reject tool calls when the model emits a tool name that doesn't
        exactly match one of the registered tools. A common failure mode is the model
        prefixing tool names with "functions/" (e.g. "functions/ContactUserTool").
        """
        text = str(exc).lower()
        return (
            "tool_use_failed" in text
            and "attempted to call tool" in text
            and "was not in request.tools" in text
            and "functions/" in text
        )

    def _build_tool_call_name_retry_instruction(self) -> str:
        return (
            "Retry the previous response. If you call a tool, the tool name must match "
            "exactly one of the registered tool names listed under # TOOLS. "
            "Do NOT prefix tool names with 'functions/' (e.g. use 'ContactUserTool', "
            "not 'functions/ContactUserTool')."
        )

    async def _route_internal_error_to_policy_system(
        self,
        failed_message_type: str,
        error_summary: str,
        task_id: int | None = None,
        contract: InvalidReviewRecoveryContract | None = None,
    ) -> None:
        if self.agent_id.type == "System5":
            return
        policy_systems = self._get_systems_by_type(SystemType.POLICY)
        if not policy_systems:
            logger.error(
                "Internal error in %s but no System5 found: %s",
                self.agent_id.__str__(),
                error_summary,
            )
            return
        await self._publish_message_to_agent(
            InternalErrorMessage(
                team_id=self.team_id,
                origin_system_id_str=self.agent_id.__str__(),
                failed_message_type=failed_message_type,
                error_summary=error_summary,
                task_id=task_id,
                contract=contract,
                content="Internal processing failure routed to System5.",
                source=self.name,
            ),
            policy_systems[0].get_agent_id(),
        )

    async def _set_system_prompt(
        self,
        message_specific_prompts: List[str] = [],
        memory_context: list[str] | None = None,
        active_tools: list[Any] | None = None,
    ) -> str:
        has_explicit_tools = active_tools is not None
        tools_for_prompt = active_tools
        if tools_for_prompt is None:
            tools_for_prompt = getattr(self, "_active_prompt_tools_override", None)
            if tools_for_prompt is not None:
                has_explicit_tools = True
        if tools_for_prompt is None:
            tools_for_prompt = self.tools
        messages: list[str] = []
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
        tool_names = {
            str(getattr(tool, "name", tool.__class__.__name__))
            for tool in tools_for_prompt
        }
        if not has_explicit_tools or "memory_crud" in tool_names:
            messages.extend(self._memory_prompt_entries())
        else:
            messages.append("Memory tool unavailable for this run.")
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
        if tools_for_prompt:
            for tool in tools_for_prompt:
                name = getattr(tool, "name", tool.__class__.__name__)
                description = getattr(tool, "description", "")
                messages.append(f"{name}: {description}")
        else:
            messages.append("No tools available")
        if message_specific_prompts:
            messages.append("# MESSAGE SPECIFIC PROMPTS")
            messages.extend(message_specific_prompts)

        compacted_messages = self._compact_prompt_messages(messages)
        self._last_system_messages = [
            SystemMessage(content=message) for message in compacted_messages
        ]
        setattr(self._agent, "_system_messages", self._last_system_messages)
        return "\n".join(compacted_messages)

    def _compact_prompt_messages(self, messages: list[str]) -> list[str]:
        max_total_chars = _env_int("SYSTEM_PROMPT_MAX_CHARS", 12000)
        max_entry_chars = _env_int("SYSTEM_PROMPT_ENTRY_MAX_CHARS", 1200)
        normalized = [
            self._truncate_prompt_entry(entry, max_entry_chars) for entry in messages
        ]
        if not normalized:
            return normalized

        joined = "\n".join(normalized)
        if len(joined) <= max_total_chars:
            return normalized

        marker = self.MESSAGE_BUDGET_TRUNCATION_NOTE
        marker_size = len(marker) + 1
        target_head = max(0, (max_total_chars - marker_size) // 2)
        target_tail = max(0, max_total_chars - marker_size - target_head)

        head: list[str] = []
        consumed_head = 0
        for entry in normalized:
            next_size = len(entry) + (1 if head else 0)
            if consumed_head + next_size > target_head:
                break
            head.append(entry)
            consumed_head += next_size

        tail: list[str] = []
        consumed_tail = 0
        for entry in reversed(normalized):
            if head and len(head) + len(tail) >= len(normalized):
                break
            next_size = len(entry) + (1 if tail else 0)
            if consumed_tail + next_size > target_tail:
                break
            tail.append(entry)
            consumed_tail += next_size
        tail.reverse()

        compacted = [*head, marker, *tail]
        while len("\n".join(compacted)) > max_total_chars and tail:
            tail = tail[1:]
            compacted = [*head, marker, *tail]
        while len("\n".join(compacted)) > max_total_chars and head:
            head = head[:-1]
            compacted = [*head, marker, *tail]
        if len("\n".join(compacted)) > max_total_chars:
            compacted = [marker[:max_total_chars]]
        return compacted

    def _truncate_prompt_entry(self, entry: str, max_entry_chars: int) -> str:
        if max_entry_chars <= 0:
            return ""
        if len(entry) <= max_entry_chars:
            return entry
        suffix = "... [truncated]"
        if max_entry_chars <= len(suffix):
            return entry[:max_entry_chars]
        return f"{entry[: max_entry_chars - len(suffix)]}{suffix}"

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

        def _should_force_onboarding_profile(text: str) -> bool:
            lowered = text.lower()
            return any(
                fragment in lowered
                for fragment in (
                    "collect user identity",
                    "disambiguation",
                    "profile links",
                    "onboarding",
                    "identity and links",
                )
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
            except (sqlite3.Error, OSError) as exc:
                logger.warning(
                    "Memory retrieval skipped for %s/%s: %s",
                    scope.value,
                    namespace,
                    exc,
                )
                continue
            entries.extend(result.items)

            # Identity collection during onboarding must be able to recall the
            # onboarding summary/profile even when semantic search misses.
            if scope == MemoryScope.GLOBAL and _should_force_onboarding_profile(
                query_text
            ):
                from src.cyberagent.memory.models import MemoryLayer

                try:
                    tagged = retrieval.search_entries(
                        actor=actor,
                        scope=scope,
                        namespace=namespace,
                        query_text=None,
                        tags=["onboarding", "user_profile"],
                        layer=MemoryLayer.LONG_TERM,
                        limit=_env_int("MEMORY_RETRIEVAL_LIMIT", 6),
                    )
                except PermissionError:
                    tagged = None
                except (sqlite3.Error, OSError) as exc:
                    logger.warning(
                        "Onboarding memory retrieval skipped for %s/%s: %s",
                        scope.value,
                        namespace,
                        exc,
                    )
                    tagged = None
                if tagged is not None:
                    entries.extend(tagged.items)

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
        response_text = (
            task_result.messages[-1].to_text() if task_result.messages else ""
        )
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
                "Permission override: you may read team and global scopes but must not write team/global."
            )
        return entries

    def _was_tool_called(self, response: TaskResult | Response, tool_name: str) -> bool:
        events: list[BaseAgentEvent] = []
        if isinstance(response, TaskResult):
            for message in response.messages:
                if isinstance(message, BaseAgentEvent):
                    events.append(message)
        else:
            for message in response.inner_messages or []:
                if isinstance(message, BaseAgentEvent):
                    events.append(message)
        for inner_message in events:
            if isinstance(inner_message, ToolCallExecutionEvent):
                for result in inner_message.content:
                    if result.name == tool_name:
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
            logger.debug("...[%s] message content: %s", self.id.__str__(), summary)
        return await self.publish_message(
            message=message,
            topic_id=TopicId(topic_type, topic_source),
        )

    def _get_systems_by_type(self, type: SystemType) -> List["System"]:  # noqa: A002
        if not self.team_id:
            raise ValueError("Team id is not set for this agent.")
        return system_service.get_systems_by_type(self.team_id, type)

    def _get_last_message(self, result: TaskResult) -> BaseChatMessage:
        if not result.messages:
            raise ValueError("No chat message received")
        last_event: BaseAgentEvent | None = None
        for message in reversed(result.messages):
            if isinstance(message, BaseChatMessage):
                return message
            if last_event is None:
                last_event = message
        if last_event is not None:
            return BaseTextChatMessage(
                source=last_event.source, content=last_event.to_text()
            )
        raise ValueError("No chat message received")

    def _get_structured_message(self, result: TaskResult, expected_type: type):
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
                except Exception as exc:
                    raise ValueError(f"Failed to parse response: {str(exc)}") from exc
            raise ValueError("No StructuredMessage found in task result")

        if isinstance(structured_message.content, expected_type):
            return structured_message.content
        try:
            if isinstance(structured_message.content, str):
                return expected_type.model_validate_json(structured_message.content)
            raise ValueError(
                f"Expected {expected_type.__name__}, got {type(structured_message.content)}"
            )
        except Exception as exc:
            raise ValueError(f"Failed to parse response: {str(exc)}") from exc
