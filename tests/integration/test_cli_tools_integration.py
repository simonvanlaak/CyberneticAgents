# Test CLI Tools + AutoGen Integration
# TDD: Write failing tests first

import os
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


# Check if Docker is available
def is_docker_available() -> bool:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


# Test 1: Dockerfile builds successfully
@pytest.mark.docker
@pytest.mark.skipif(not is_docker_available(), reason="Docker daemon not running")
def test_dockerfile_builds():
    """Test that the CLI tools Docker image builds successfully."""
    result = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            "cli-tools:test",
            "-f",
            "src/cyberagent/tools/cli_executor/Dockerfile.cli-tools",
            ".",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Docker build failed: {result.stderr}"


# Test 2: Docker executor can run CLI commands
@pytest.mark.asyncio
async def test_cli_tool_command_execution() -> None:
    """Test that CLI commands can be executed via Docker executor."""
    from src.cyberagent.tools.cli_executor.cli_tool import CliTool

    # Mock successful execution
    mock_execute = AsyncMock(
        return_value=SimpleNamespace(
            exit_code=0,
            output='{"success": true, "result": "test output"}',
            code_file="/workspace/tmp_test.py",
        )
    )

    executor = AsyncMock()
    executor.execute_code_blocks = mock_execute

    tool = CliTool(executor)
    tool._check_permission = lambda *_args, **_kwargs: True
    result = await tool.execute("git", subcommand="--version", agent_id="System4/root")

    assert result["success"] is True
    assert "result" in result["output"]
    mock_execute.assert_called_once()


# Test 3: Web search tool works
@pytest.mark.asyncio
@patch("src.cyberagent.tools.cli_executor.cli_tool.CliTool.execute")
async def test_web_search_integration(mock_execute: AsyncMock) -> None:
    """Test that web_search can be called through the CLI tools integration."""
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

    from src.cyberagent.tools.cli_executor.cli_tool import CliTool

    result = await CliTool(None).execute("web_search", query="test", count=1)

    assert result["success"] is True
    assert len(result["output"]["results"]) == 1
    mock_execute.assert_called_with("web_search", query="test", count=1)


# Test 4: RBAC enforcement
@pytest.mark.asyncio
async def test_rbac_enforcement() -> None:
    """Test that RBAC prevents unauthorized tool usage."""
    from src.cyberagent.tools.cli_executor.cli_tool import CliTool

    # Mock RBAC to deny access
    with patch("src.rbac.enforcer.check_tool_permission", return_value=False):
        result = await CliTool(None).execute("exec", agent_id="unauthorized_agent")

        assert result["success"] is False
        assert "not authorized" in result["error"]


# Test 5: Real integration test (requires Docker)
@pytest.mark.asyncio
@pytest.mark.docker
@pytest.mark.skipif(
    not is_docker_available() or os.getenv("RUN_CLI_TOOLS_INTEGRATION") != "1",
    reason="Docker integration tests are opt-in.",
)
async def test_real_cli_tool_execution() -> None:
    """Integration test with real Docker executor (requires Docker running)."""
    from src.cyberagent.tools.cli_executor.factory import create_cli_executor
    from src.cyberagent.tools.cli_executor.cli_tool import CliTool

    executor = create_cli_executor()
    if executor is None:
        pytest.skip("Docker executor not available")
    tool = CliTool(executor)

    await executor.start()
    try:
        result = await tool.execute(
            "git", subcommand="--version", agent_id="System4/root"
        )
    finally:
        await executor.stop()

    assert result["success"] is True
    assert "git version" in result["output"]
