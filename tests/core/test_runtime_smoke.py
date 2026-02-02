from __future__ import annotations

import types
from typing import Optional

import pytest

from src.cyberagent.core import runtime as runtime_module


def test_configure_tracing_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert runtime_module.configure_tracing() is None


def test_get_runtime_starts_once(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_module._runtime = None

    calls: dict[str, int] = {"start": 0}

    class DummyRuntime:
        def __init__(self, tracer_provider: Optional[object] = None) -> None:
            self.tracer_provider = tracer_provider

        def start(self) -> None:
            calls["start"] += 1

    monkeypatch.setattr(runtime_module, "SingleThreadedAgentRuntime", DummyRuntime)
    monkeypatch.setattr(runtime_module, "create_cli_executor", lambda: object())
    first = runtime_module.get_runtime()
    second = runtime_module.get_runtime()
    assert first is second
    assert calls["start"] == 1


@pytest.mark.asyncio
async def test_stop_runtime_noop_when_unset() -> None:
    runtime_module._runtime = None
    await runtime_module.stop_runtime()
