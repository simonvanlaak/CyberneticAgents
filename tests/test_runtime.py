from __future__ import annotations

import pytest

from src.cyberagent.core import runtime as runtime_module
from src.cyberagent.tools.cli_executor import factory as factory_module


def test_configure_tracing_returns_none_without_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    assert runtime_module.configure_tracing() is None


def test_configure_tracing_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret")

    class DummyLangfuse:
        def auth_check(self) -> bool:
            return False

    monkeypatch.setattr(runtime_module, "Langfuse", DummyLangfuse)

    assert runtime_module.configure_tracing() is None


def test_configure_tracing_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://example.test/langfuse")

    class DummyLangfuse:
        def auth_check(self) -> bool:
            return True

    class DummyExporter:
        def __init__(self, endpoint: str, headers: dict[str, str]) -> None:
            self.endpoint = endpoint
            self.headers = headers

    class DummyBatchProcessor:
        def __init__(self, exporter: DummyExporter) -> None:
            self.exporter = exporter

        def shutdown(self) -> None:
            return None

    captured: dict[str, object] = {}

    def fake_set_tracer_provider(provider: object) -> None:
        captured["provider"] = provider

    monkeypatch.setattr(runtime_module, "Langfuse", DummyLangfuse)
    monkeypatch.setattr(runtime_module, "OTLPSpanExporter", DummyExporter)
    monkeypatch.setattr(runtime_module, "BatchSpanProcessor", DummyBatchProcessor)
    monkeypatch.setattr(
        runtime_module.trace, "set_tracer_provider", fake_set_tracer_provider
    )

    provider = runtime_module.configure_tracing()

    assert provider is captured["provider"]


def test_get_runtime_starts_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_module._runtime = None

    class DummyRuntime:
        def __init__(self, tracer_provider=None) -> None:
            self.tracer_provider = tracer_provider
            self.start_count = 0

        def start(self) -> None:
            self.start_count += 1

        async def stop_when_idle(self) -> None:
            return None

    monkeypatch.setattr(runtime_module, "SingleThreadedAgentRuntime", DummyRuntime)
    monkeypatch.setattr(runtime_module, "configure_tracing", lambda: "trace")

    first = runtime_module.get_runtime()
    second = runtime_module.get_runtime()

    assert first is second
    assert first.start_count == 1


def test_create_cli_executor_uses_configured_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_image = "ghcr.io/example/openclaw-tools:latest"
    monkeypatch.setenv("OPENCLAW_TOOLS_IMAGE", expected_image)

    captured: dict[str, object] = {}

    class DummyExecutor:
        def __init__(self, *args, **kwargs) -> None:
            captured["image"] = kwargs.get("image")

    monkeypatch.setattr(
        factory_module, "EnvDockerCommandLineCodeExecutor", DummyExecutor
    )

    executor = factory_module.create_cli_executor()

    assert executor is not None
    assert captured["image"] == expected_image


@pytest.mark.asyncio
async def test_stop_runtime_clears_instance() -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.stopped = False

        async def stop_when_idle(self) -> None:
            self.stopped = True

    runtime_module._runtime = DummyRuntime()

    await runtime_module.stop_runtime()

    assert runtime_module._runtime is None


@pytest.mark.asyncio
async def test_stop_runtime_noop_when_none() -> None:
    runtime_module._runtime = None

    await runtime_module.stop_runtime()

    assert runtime_module._runtime is None
