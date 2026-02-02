# -*- coding: utf-8 -*-
"""
Central runtime manager for the VSM multi-agent system.
"""

import base64
import logging
import os

from autogen_core import SingleThreadedAgentRuntime
from langfuse import Langfuse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.cyberagent.tools.cli_executor.docker_env_executor import (
    EnvDockerCommandLineCodeExecutor,
)
from src.cyberagent.tools.cli_executor.factory import create_cli_executor

# Singleton runtime instance
_runtime: SingleThreadedAgentRuntime | None = None
_cli_executor: EnvDockerCommandLineCodeExecutor | None = None
logger = logging.getLogger(__name__)


def configure_tracing():
    """Configure OpenTelemetry tracing with Langfuse integration."""
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")

    if not public_key or not secret_key:
        logger.info("Langfuse credentials not found, running without tracing")
        return None

    try:
        langfuse = Langfuse()

        if langfuse.auth_check():
            logger.info("Langfuse client is authenticated and ready.")
        else:
            logger.warning("Langfuse authentication failed. Check credentials/host.")
            return None

        tracer_provider = TracerProvider(
            resource=Resource({"service.name": "cybernetic-agents"})
        )

        auth_string = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

        langfuse_endpoint = os.environ.get(
            "LANGFUSE_BASE_URL", "https://cloud.langfuse.com"
        )
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{langfuse_endpoint}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {auth_string}"},
        )

        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(tracer_provider)

        return tracer_provider
    except Exception as e:
        logger.warning("Failed to configure tracing: %s. Running without tracing.", e)
        return None


def get_runtime() -> SingleThreadedAgentRuntime:
    """Get the singleton runtime instance with OpenTelemetry tracing."""
    global _runtime
    global _cli_executor
    if _runtime is None:
        _runtime = SingleThreadedAgentRuntime(tracer_provider=configure_tracing())
        _cli_executor = create_cli_executor()
        _runtime.start()
    return _runtime


def get_cli_executor() -> EnvDockerCommandLineCodeExecutor | None:
    """Return the shared CLI executor instance if available."""
    return _cli_executor


async def start_cli_executor() -> None:
    """Start the shared CLI executor container if configured."""
    executor = _cli_executor
    if executor is None:
        return
    if getattr(executor, "_running", False):
        return
    try:
        await executor.start()
    except Exception as exc:
        logger.warning("Failed to start CLI executor: %s", exc)


async def stop_cli_executor() -> None:
    """Stop the shared CLI executor container if running."""
    executor = _cli_executor
    if executor is None:
        return
    try:
        await executor.stop()
    except Exception as exc:
        logger.warning("Failed to stop CLI executor: %s", exc)


async def stop_runtime() -> None:
    """Stop the runtime gracefully."""
    global _runtime
    if _runtime is None:
        return
    await _runtime.stop_when_idle()
    await stop_cli_executor()
    _runtime = None
