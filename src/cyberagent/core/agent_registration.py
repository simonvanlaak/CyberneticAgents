"""Runtime-scoped registration tracking for agent type factories."""

from __future__ import annotations

from collections import defaultdict

_registered_by_runtime: dict[int, set[str]] = defaultdict(set)


def is_registered(runtime: object, agent_type: str) -> bool:
    """Return True when the given runtime already has the agent type registered."""
    return agent_type in _registered_by_runtime[id(runtime)]


def mark_registered(runtime: object, agent_type: str) -> None:
    """Record that the runtime has registered the given agent type."""
    _registered_by_runtime[id(runtime)].add(agent_type)


def clear_runtime(runtime: object) -> None:
    """Clear tracked registrations for a runtime instance."""
    _registered_by_runtime.pop(id(runtime), None)


def reset_for_tests() -> None:
    """Reset all in-memory registration tracking (tests only)."""
    _registered_by_runtime.clear()
