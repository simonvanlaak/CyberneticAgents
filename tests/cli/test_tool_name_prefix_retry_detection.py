from __future__ import annotations

from src.agents.system_base_mixin import SystemBaseMixin


class _Dummy(SystemBaseMixin):
    """Concrete instance to exercise the mixin helpers."""


def test_detects_namespaced_tool_name_provider_error() -> None:
    dummy = _Dummy()
    exc = Exception(
        "Error code: 400 - {'error': {'message': \"Tool call validation failed: tool call validation failed: attempted to call tool 'functions/ContactUserTool' which was not in request.tools\", 'code': 'tool_use_failed'}}"
    )
    assert dummy._is_tool_call_name_validation_error(exc) is True


def test_builds_retry_instruction_for_namespaced_tool_name() -> None:
    dummy = _Dummy()
    instr = dummy._build_tool_call_name_retry_instruction()
    assert "functions/ContactUserTool" in instr
    assert "ContactUserTool" in instr
