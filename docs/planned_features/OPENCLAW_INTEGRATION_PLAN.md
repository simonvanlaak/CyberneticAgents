# OpenClaw + AutoGen Integration Plan

## 🎯 Goal
Make OpenClaw's existing CLI tools and skills available to all AutoGen VSM agents with minimal effort, using AutoGen's Docker command line executor.

## 🔧 Current State

### AutoGen Side
- **DockerCommandLineCodeExecutor**: Executes commands in a Docker container
- Supports Python and shell scripts
- Can mount host directories and Docker socket
- Default image: `python:3-slim`

### OpenClaw Side
- **Existing tools**: `web_search`, `web_fetch`, `read`, `write`, `exec`, etc.
- **CLI interface**: All tools accessible via `openclaw` CLI
- **Skills ecosystem**: Pre-installed skills with standardized interfaces

## 🚀 Integration Strategy

### Option 1: Docker-in-Docker (Recommended)
```
┌─────────────────────────────────────────────────────┐
│ CyberneticAgents (AutoGen) Container                │
│                                                     │
│  ┌─────────────┐    ┌───────────────────────────┐  │
│  │ VSM Agents  │───▶│ DockerCommandLineExecutor│  │
│  └─────────────┘    └───────────────────────────┘  │
│           │                                   │      │
│           ▼                                   ▼      │
│  ┌─────────────┐    ┌───────────────────────────┐  │
│  │   SQLite    │    │ OpenClaw Tools Container  │  │
│  └─────────────┘    └───────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**How it works:**
1. CyberneticAgents runs in a Docker container
2. Mount Docker socket (`-v /var/run/docker.sock:/var/run/docker.sock`)
3. AutoGen's Docker executor spawns **sibling containers** for OpenClaw tools
4. VSM agents can execute any OpenClaw CLI command in isolated containers

### Option 2: Local Execution (Simpler but Less Safe)
```
┌─────────────────────────────────────────────────────┐
│ CyberneticAgents (AutoGen)                         │
│                                                     │
│  ┌─────────────┐    ┌───────────────────────────┐  │
│  │ VSM Agents  │───▶│ LocalCommandLineExecutor │  │
│  └─────────────┘    └───────────────────────────┘  │
│           │                                   │      │
│           ▼                                   ▼      │
│  ┌─────────────┐    ┌───────────────────────────┐  │
│  │   SQLite    │    │ OpenClaw CLI (on host)    │  │
│  └─────────────┘    └───────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**How it works:**
1. Install OpenClaw CLI on host machine
2. Use AutoGen's `LocalCommandLineCodeExecutor`
3. VSM agents execute OpenClaw commands directly on host

## ✅ Recommended Approach: Option 1 (Docker-in-Docker)

### **Why Docker-in-Docker?**
- **Isolation**: Each tool execution runs in its own container
- **Reproducibility**: Consistent environment for all agents
- **Security**: Containers limit blast radius of tool execution
- **Scalability**: Easy to add new tools/skills
- **Multi-agent safe**: Each agent gets its own execution context

### **Implementation Steps**

#### 1. Create OpenClaw Tools Docker Image
```dockerfile
# Dockerfile.openclaw-tools (src/tools/cli_executor)
FROM python:3.11-slim

# Install OpenClaw and dependencies
RUN npm install -g openclaw@latest

# Install common skills
# Optional: install extra OpenClaw skills here

# Install system dependencies for skills
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set up workspace
RUN mkdir -p /workspace
WORKDIR /workspace

# Copy any custom configs
COPY .openclaw.json /root/.openclaw.json

ENTRYPOINT ["openclaw"]
```

#### 2. Configure AutoGen Docker Executor
```python
# src/runtime.py
from pathlib import Path
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor

def create_openclaw_executor():
    work_dir = Path("coding")
    work_dir.mkdir(exist_ok=True)
    
    return DockerCommandLineCodeExecutor(
        work_dir=work_dir,
        image="openclaw-tools:latest",  # Our custom image
        container_name="openclaw-tools-executor",
        auto_remove=True,  # Clean up after execution
        # Mount workspace for file access
        volumes={
            str(work_dir.absolute()): {
                "bind": "/workspace",
                "mode": "rw"
            }
        },
        # Allow Docker-in-Docker
        docker_socket_path="/var/run/docker.sock"
    )
```

#### 3. Create OpenClaw Tool Wrapper
```python
# src/tools/openclaw_tool.py
from autogen_core.code_executor import CodeBlock
from typing import Optional, Dict, Any

class OpenClawTool:
    def __init__(self, executor):
        self.executor = executor
    
    async def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute an OpenClaw tool with given parameters.
        
        Args:
            tool_name: Name of the OpenClaw tool (e.g., "web_search", "exec")
            **kwargs: Parameters for the tool
            
        Returns:
            Dictionary with tool output
        """
        # Convert kwargs to CLI arguments
        args = " ".join([f"--{k} {v}" for k, v in kwargs.items()])
        
        # Create shell command
        command = f"openclaw {tool_name} {args}"
        
        # Execute in Docker container
        result = await self.executor.execute_code_blocks(
            code_blocks=[
                CodeBlock(language="bash", code=command)
            ]
        )
        
        # Parse output (assuming JSON output from OpenClaw tools)
        if result.exit_code == 0:
            return {"success": True, "output": result.output}
        else:
            return {"success": False, "error": result.output}
```

#### 4. Integrate with VSM Agents
```python
# src/agents/vsm_agent.py
from src.runtime import create_openclaw_executor
from src.tools.openclaw_tool import OpenClawTool

class VSMSystemAgent(RoutedAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executor = create_openclaw_executor()
        self.openclaw = OpenClawTool(self.executor)
    
    @message_handler
    async def handle_discovery(self, message: DelegateMessage) -> DelegateMessage:
        # Example: Use web_search tool
        search_result = await self.openclaw.execute(
            "web_search",
            query="Simon van Laak product management",
            count=3
        )
        
        if search_result["success"]:
            return DelegateMessage(
                content=f"Found user info: {search_result['output']}",
                recipient=message.sender
            )
        else:
            return DelegateMessage(
                content=f"Search failed: {search_result['error']}",
                recipient=message.sender
            )
```

#### 5. Build and Test
```bash
# Build the OpenClaw tools image
docker build -t openclaw-tools:latest -f src/tools/cli_executor/Dockerfile.openclaw-tools .

# Test the integration
python -m pytest tests/integration/test_openclaw_integration.py -v
```

## 🧪 Example Use Cases

### 1. Web Search (System 4 Intelligence)
```python
result = await agent.openclaw.execute(
    "web_search",
    query="current trends in LLM adoption engineering departments",
    count=5
)
```

### 2. File Access (System 4 Discovery)
```python
# Check what files are accessible
result = await agent.openclaw.execute("exec", command="ls -la ~/Documents")

# Read a file
result = await agent.openclaw.execute(
    "read",
    path="/workspace/user_notes.md"
)
```

### 3. Execute Commands (System 1 Operations)
```python
# Run a system command
result = await agent.openclaw.execute(
    "exec",
    command="git status",
    workdir="/workspace/CyberneticAgents"
)
```

### 4. Use Skills (System 1-5 Capabilities)
```python
# Run the coding-agent skill
result = await agent.openclaw.execute(
    "coding-agent",
    command="codex exec 'Write a test for the discovery system'",
    pty=True,
    background=True
)
```

## 🔐 Security Considerations

### 1. RBAC Integration
```python
# src/rbac/enforcer.py
from casbin import Enforcer

def check_tool_permission(agent_id: str, tool_name: str) -> bool:
    """
    Check if agent has permission to use a tool.
    
    Example policy:
    p, root_intelligence_sys4, web_search, allow
    p, root_control_sys3, exec, allow
    p, root_operations_sys1, read, allow
    """
    enforcer = get_enforcer()
    return enforcer.enforce(agent_id, tool_name, "allow")
```

### 2. Tool Wrapper with RBAC
```python
# src/tools/openclaw_tool.py
async def execute(self, tool_name: str, agent_id: str, **kwargs) -> Dict[str, Any]:
    # Check RBAC permission
    if not check_tool_permission(agent_id, tool_name):
        return {
            "success": False,
            "error": f"Agent {agent_id} not authorized to use {tool_name}"
        }
    
    # Proceed with execution...
```

## 📊 Monitoring & Observability

### 1. Tool Usage Logging
```python
# src/tools/openclaw_tool.py
import logging

logger = logging.getLogger(__name__)

async def execute(self, tool_name: str, agent_id: str, **kwargs) -> Dict[str, Any]:
    logger.info(f"Agent {agent_id} executing {tool_name} with args: {kwargs}")
    
    try:
        result = await self._execute_in_docker(tool_name, kwargs)
        logger.info(f"Tool {tool_name} completed with status: {result['success']}")
        return result
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {str(e)}")
        return {"success": False, "error": str(e)}
```

### 2. Langfuse Tracing (Optional)
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def execute(self, tool_name: str, agent_id: str, **kwargs):
    with tracer.start_as_current_span(f"openclaw.{tool_name}") as span:
        span.set_attribute("agent.id", agent_id)
        span.set_attribute("tool.name", tool_name)
        
        # Execute tool...
        
        span.set_attribute("tool.success", result["success"])
        if not result["success"]:
            span.record_exception(Exception(result["error"]))
```

## 🧩 Extensibility

### Adding New Tools/Skills
1. **Install the skill** in the Docker image (`src/tools/cli_executor/Dockerfile.openclaw-tools`)
2. **Add RBAC policy** for which agents can use it
3. **Use it** via the OpenClawTool wrapper

### Example: Adding Weather Skill
```dockerfile
# Dockerfile.openclaw-tools (src/tools/cli_executor)
# Optional: install extra OpenClaw skills here
```

```python
# RBAC policy (in src/rbac/model.conf)
p, root_intelligence_sys4, weather, allow
```

```python
# Usage in agent
result = await agent.openclaw.execute("weather", location="Berlin")
```

## 🧪 Testing Strategy

### 1. Unit Tests
```python
# tests/tools/test_openclaw_tool.py
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_web_search():
    mock_executor = AsyncMock()
    mock_executor.execute_code_blocks.return_value = CommandLineCodeResult(
        exit_code=0,
        output='{"results": [{"title": "Test", "url": "http://test.com"}]}'
    )
    
    tool = OpenClawTool(mock_executor)
    result = await tool.execute("web_search", query="test", count=1)
    
    assert result["success"] is True
    assert "results" in result["output"]
```

### 2. Integration Tests
```python
# tests/integration/test_openclaw_integration.py
import pytest
from src.runtime import create_openclaw_executor
from src.tools.openclaw_tool import OpenClawTool

@pytest.mark.asyncio
async def test_real_web_search():
    executor = create_openclaw_executor()
    tool = OpenClawTool(executor)
    
    result = await tool.execute("web_search", query="OpenClaw AI", count=1)
    
    assert result["success"] is True
    assert len(result["output"]["results"]) == 1
```

### 3. RBAC Tests
```python
# tests/rbac/test_openclaw_rbac.py
import pytest
from src.rbac.enforcer import check_tool_permission

def test_sys4_can_use_web_search():
    assert check_tool_permission("root_intelligence_sys4", "web_search") is True

def test_sys1_cannot_use_exec():
    assert check_tool_permission("root_operations_sys1", "exec") is False
```

## 📈 Roadmap

### Phase 1: Core Integration (Now)
- [ ] Create OpenClaw tools Docker image
- [ ] Implement DockerCommandLineCodeExecutor
- [ ] Create OpenClawTool wrapper
- [ ] Integrate with VSM agents
- [ ] Add RBAC enforcement
- [ ] Write tests

### Phase 2: Enhanced Discovery
- [ ] Build discovery interview system using OpenClaw tools
- [ ] Implement user identity discovery (web search)
- [ ] Add file access audit
- [ ] Create automated analysis pipeline

### Phase 3: Tool Ecosystem Expansion
- [ ] Add more OpenClaw skills to the Docker image
- [ ] Implement skill-specific wrappers
- [ ] Add tool usage analytics
- [ ] Create tool recommendation system

## 🎯 Success Criteria

✅ **All VSM agents** can access OpenClaw tools via standardized interface
✅ **RBAC enforcement** prevents unauthorized tool usage
✅ **Docker isolation** ensures safe execution
✅ **Minimal code changes** to existing CyberneticAgents codebase
✅ **Full test coverage** (70% minimum, enforced by git hooks)
✅ **Atomic commits** with clear, focused changes

## 🚀 Next Steps

1. **Review this plan** - Any adjustments needed?
2. **Create Dockerfile** for OpenClaw tools image
3. **Implement executor** in `src/runtime.py`
4. **Build OpenClawTool wrapper**
5. **Integrate with VSM agents**
6. **Add RBAC policies** for tool access
7. **Write tests** (TDD workflow)

Should I proceed with implementing Phase 1? 🚀
