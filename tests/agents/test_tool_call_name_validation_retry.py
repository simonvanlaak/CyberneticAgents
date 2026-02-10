import pytest

from src.agents.system_base_mixin import SystemBaseMixin


class Dummy(SystemBaseMixin):
    """Minimal concrete class to exercise mixin helpers."""

    # SystemBaseMixin expects these attributes to exist in some paths, but our
    # tests only call pure helper methods.
    agent_id = None  # type: ignore[assignment]
    team_id = 0
    name = "dummy"
    identity_prompt = ""
    responsibility_prompts = []
    tools = []
    _agent = None
    _last_system_messages = []
    _session_recorder = None
    publish_message = None


def test_is_tool_call_name_validation_error_detects_functions_prefix() -> None:
    dummy = Dummy()
    exc = RuntimeError(
        "Tool call validation failed: attempted to call tool 'functions/ContactUserTool' which was not in request.tools (tool_use_failed)"
    )
    assert dummy._is_tool_call_name_validation_error(exc) is True


def test_is_tool_call_name_validation_error_false_for_other_errors() -> None:
    dummy = Dummy()
    exc = RuntimeError("Some other provider error")
    assert dummy._is_tool_call_name_validation_error(exc) is False


def test_build_tool_call_name_retry_instruction_mentions_functions_prefix() -> None:
    dummy = Dummy()
    instruction = dummy._build_tool_call_name_retry_instruction()
    assert "functions/" in instruction
    assert "Do NOT" in instruction
