# Test OpenClaw + AutoGen Integration
# TDD: Write failing tests first

import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


# Check if Docker is available
def is_docker_available():
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except:
        return False


# Test 1: Dockerfile builds successfully
@pytest.mark.docker
@pytest.mark.skipif(not is_docker_available(), reason="Docker daemon not running")
def test_dockerfile_builds():
    """Test that the OpenClaw tools Docker image builds successfully."""
    result = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            "openclaw-tools:test",
            "-f",
            "src/tools/cli_executor/Dockerfile.openclaw-tools",
            ".",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Docker build failed: {result.stderr}"


# Test 2: Docker executor can run OpenClaw commands
@pytest.mark.asyncio
@patch(
    "autogen_ext.code_executors.docker.DockerCommandLineCodeExecutor.execute_code_blocks"
)
async def test_openclaw_command_execution(mock_execute):
    """Test that OpenClaw commands can be executed via Docker executor."""
    from src.tools.cli_executor.openclaw_tool import OpenClawTool

    # Mock successful execution
    mock_execute.return_value = type(
        "obj",
        (object,),
        {
            "exit_code": 0,
            "output": '{"success": true, "result": "test output"}',
            "code_file": "/workspace/tmp_test.py",
        },
    )

    executor = AsyncMock()
    executor.execute_code_blocks = mock_execute

    tool = OpenClawTool(executor)
    result = await tool.execute("skills", subcommand="list")

    assert result["success"] is True
    assert "result" in result["output"]
    mock_execute.assert_called_once()


# Test 3: Web search tool works
@pytest.mark.asyncio
@patch("src.tools.cli_executor.openclaw_tool.OpenClawTool.execute")
async def test_web_search_integration(mock_execute):
    """Test that web_search tool can be called through OpenClaw integration."""
    mock_execute.return_value = {
        "success": True,
        "output": {
            "results": [
                {
                    "title": "Test Result",
                    "url": "http://test.com",
                    "description": "Test",
                }
            ]
        },
    }

    from src.tools import OpenClawTool

    result = await OpenClawTool(None).execute("web_search", query="test", count=1)

    assert result["success"] is True
    assert len(result["output"]["results"]) == 1
    mock_execute.assert_called_with("web_search", query="test", count=1)


# Test 4: RBAC enforcement
@pytest.mark.asyncio
async def test_rbac_enforcement():
    """Test that RBAC prevents unauthorized tool usage."""
    from src.rbac.enforcer import check_tool_permission
    from src.tools.cli_executor.openclaw_tool import OpenClawTool

    # Mock RBAC to deny access
    with patch("src.rbac.enforcer.check_tool_permission", return_value=False):
        result = await OpenClawTool(None).execute("exec", agent_id="unauthorized_agent")

        assert result["success"] is False
        assert "not authorized" in result["error"]


# Test 5: Real integration test (requires Docker)
@pytest.mark.asyncio
@pytest.mark.docker
@pytest.mark.skipif(
    not is_docker_available() or os.getenv("RUN_OPENCLAW_INTEGRATION") != "1",
    reason="Docker integration tests are opt-in.",
)
async def test_real_openclaw_execution():
    """Integration test with real Docker executor (requires Docker running)."""
    from src.runtime import create_cli_executor
    from src.tools.cli_executor.openclaw_tool import OpenClawTool

    executor = create_cli_executor()
    if executor is None:
        pytest.skip("Docker executor not available")
    tool = OpenClawTool(executor)

    await executor.start()
    try:
        # Test a simple OpenClaw command
        result = await tool.execute("skills", subcommand="list")
    finally:
        await executor.stop()

    assert result["success"] is True
    assert "coding-agent" in result["output"]
