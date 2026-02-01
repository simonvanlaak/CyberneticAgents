# -*- coding: utf-8 -*-
"""
Central runtime manager for the VSM multi-agent system.
"""

import base64
import os
from pathlib import Path
from typing import Optional

from autogen_core import SingleThreadedAgentRuntime
from langfuse import Langfuse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.tools.cli_executor.docker_env_executor import EnvDockerCommandLineCodeExecutor

# Singleton runtime instance
_runtime: SingleThreadedAgentRuntime | None = None
_cli_executor: EnvDockerCommandLineCodeExecutor | None = None


def create_cli_executor() -> Optional[EnvDockerCommandLineCodeExecutor]:
    """
    Create a code executor for OpenClaw tools.

    Returns:
        Code executor instance or None if AutoGen not available
    """

    # Set up working directory
    work_dir = Path("data/docker_cli_executor")
    work_dir.mkdir(exist_ok=True)

    try:
        image = os.getenv(
            "OPENCLAW_TOOLS_IMAGE",
            "ghcr.io/simonvanlaak/cyberneticagents-openclaw-tools:latest",
        )
        return EnvDockerCommandLineCodeExecutor(
            work_dir=work_dir,
            image=image,
            container_name="cybernetic-agents-cli-executor",
            auto_remove=True,  # Clean up after execution
            # Note: volumes and docker_socket_path not supported in this AutoGen version
            # File access will work through work_dir mounting
        )

    except Exception:
        return None


def configure_tracing():
    """Configure OpenTelemetry tracing with Langfuse integration."""
    # Check if Langfuse credentials are available
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")

    if not public_key or not secret_key:
        print("Langfuse credentials not found, running without tracing")
        return None

    try:
        # Initialize Langfuse client
        langfuse = Langfuse()

        # Verify connection
        if langfuse.auth_check():
            print("Langfuse client is authenticated and ready!")
        else:
            print("Authentication failed. Please check your credentials and host.")
            return None

        # Configure OpenTelemetry TracerProvider with Langfuse exporter
        tracer_provider = TracerProvider(
            resource=Resource({"service.name": "cybernetic-agents"})
        )

        # Get Langfuse credentials for OTLP authentication
        auth_string = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

        # Configure OTLP exporter for Langfuse
        langfuse_endpoint = os.environ.get(
            "LANGFUSE_BASE_URL", "https://cloud.langfuse.com"
        )
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{langfuse_endpoint}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {auth_string}"},
        )

        # Add span processor
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(tracer_provider)

        return tracer_provider
    except Exception as e:
        print(f"Failed to configure tracing: {e}. Running without tracing.")
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


async def stop_runtime() -> None:
    """Stop the runtime gracefully."""
    global _runtime
    if _runtime is None:
        return
    await _runtime.stop_when_idle()
    _runtime = None
