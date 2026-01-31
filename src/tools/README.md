# Tools Implementation Guide

This guide explains how to implement new tools for the Cybernetic Agents system, following the patterns established in `delegate.py` and `escalate.py`.

## Tool Architecture Overview

Each tool consists of three main components:

1. **ArgsType**: Defines the input arguments for the tool (must inherit from `BaseModel`)
2. **Request**: Defines the message format sent to other agents (dataclass)
3. **Response**: Defines the response format returned by the tool (dataclass)
4. **Main Tool Class**: The actual tool implementation (inherits from `BaseTool`)

## Step-by-Step Implementation Guide

### 1. Required Imports

```python
from dataclasses import dataclass
from pydantic import BaseModel

from autogen_core import AgentId, CancellationToken
from autogen_core.tools import BaseTool

from src.tools.rbac_tool_helper import RBACToolHelper
```

### 2. Define ArgsType (Tool Input Arguments)

Use `BaseModel` for automatic JSON schema generation:

```python
class MyToolArgsType(BaseModel):
    parameter1: str
    parameter2: int
    # Add other parameters as needed
```

**Important**: Must inherit from `BaseModel`, not `@dataclass`, to provide the required `model_json_schema` method.

### 3. Define Request Message

```python
@dataclass
class MyToolRequest:
    content: str
    sender: str
    # Add other request fields as needed
```

### 4. Define Response Message

```python
@dataclass
class MyToolResponse:
    content: str
    success: bool
    # Add other response fields as needed
```

### 5. Implement the Main Tool Class

```python
class MyTool(BaseTool):
    agent_id: AgentId

    def __init__(self, agent_id: AgentId):
        name = __class__.__name__
        self.agent_id = agent_id
        self.rbac_tool_helper = RBACToolHelper(agent_id, name)

        # Get allowed actions from RBAC
        allowed_targets = self.rbac_tool_helper.get_allowed_actions()

        # Create tool description
        if allowed_targets:
            targets_list = ", ".join(allowed_targets)
            description = (
                f"Description of what this tool does. "
                f"Possible targets/actions: {targets_list}"
            )
        else:
            raise ValueError("No targets/actions available for this tool.")

        # Initialize base tool
        super().__init__(
            args_type=MyToolArgsType,
            return_type=MyToolResponse,
            name=name,
            description=description,
        )

    async def run(
        self, args: MyToolArgsType, cancellation_token: CancellationToken
    ) -> MyToolResponse:
        """Execute the tool's functionality."""

        # Check RBAC permissions
        if not self.rbac_tool_helper.is_action_allowed(args.target_parameter):
            raise PermissionError(f"Not allowed to perform action on {args.target_parameter}")

        # Create request message
        request_message = MyToolRequest(
            content=args.content,
            sender=self.agent_id.key,
            # Add other request fields
        )

        # Send message via runtime
        from runtime import get_runtime
        runtime = get_runtime()

        result: MyToolResponse = await runtime.send_message(
            request_message,
            recipient=AgentId(self.agent_id.type, args.target_agent_id),
            sender=self.agent_id,
        )

        return result
```

## Key Patterns and Best Practices

### RBAC Integration

- **Always use RBACToolHelper**: Every tool should use `RBACToolHelper` for permission checking
- **Check permissions early**: Validate permissions before attempting any operations
- **Dynamic descriptions**: Include allowed targets/actions in the tool description

### Error Handling

- **Permission errors**: Use `PermissionError` for RBAC violations
- **Validation errors**: Let Pydantic handle input validation automatically
- **Runtime errors**: Handle message sending failures gracefully

### Message Routing

- **Use runtime.send_message()**: Always route messages through the runtime
- **Proper recipient format**: Use `AgentId(self.agent_id.type, target_id)`
- **Include sender information**: Always set the sender field in request messages

### Message Handlers

**CRITICAL**: For your tool to work, the recipient agent must have a corresponding message handler:

```python
@message_handler
async def handle_my_tool_request(
    self,
    message: MyToolRequest,
    ctx: CancellationToken,
) -> MyToolResponse:
    """Handle incoming MyToolRequest messages."""
    # Process the request and return appropriate response
    result = await self._process_request(message)
    return MyToolResponse(content=result, success=True)
```

**Important**: The handler must:
- Use the `@message_handler` decorator
- Accept the exact Request type as parameter
- Return the exact Response type
- Be implemented in the recipient agent class

## Common Message Handler Patterns

### Basic Handler Structure

```python
@message_handler
async def handle_my_tool_request(
    self,
    message: MyToolRequest,
    ctx: CancellationToken,
) -> MyToolResponse:
    """Handle MyToolRequest messages."""
    print(f"[{self.agent_id.key}] Received request: {message.content}")

    # Process the request
    result = await self._agent.run(task=message.content)

    return MyToolResponse(content=result, success=True)
```

### Handler with Error Handling

```python
@message_handler
async def handle_my_tool_request(
    self,
    message: MyToolRequest,
    ctx: CancellationToken,
) -> MyToolResponse:
    """Handle MyToolRequest messages with error handling."""
    try:
        print(f"[{self.agent_id.key}] Processing request from {message.sender}")

        result = await self._process_request(message)
        return MyToolResponse(content=result, success=True)

    except Exception as e:
        print(f"[{self.agent_id.key}] Error processing request: {e}")
        return MyToolResponse(content=str(e), success=False)
```

## Complete Example Template

```python
from dataclasses import dataclass
from pydantic import BaseModel

from autogen_core import AgentId, CancellationToken
from autogen_core.tools import BaseTool

from src.tools.rbac_tool_helper import RBACToolHelper


class MyToolArgsType(BaseModel):
    target_agent_id: str
    task_description: str


@dataclass
class MyToolRequest:
    content: str
    sender: str
    target_agent_id: str


@dataclass
class MyToolResponse:
    content: str
    success: bool


class MyTool(BaseTool):
    agent_id: AgentId

    def __init__(self, agent_id: AgentId):
        name = __class__.__name__
        self.agent_id = agent_id
        self.rbac_tool_helper = RBACToolHelper(agent_id, name)

        allowed_targets = self.rbac_tool_helper.get_allowed_actions()

        if allowed_targets:
            targets_list = ", ".join(allowed_targets)
            description = (
                f"Perform some action using this tool. "
                f"Possible targets: {targets_list}"
            )
        else:
            raise ValueError("No targets available for MyTool.")

        super().__init__(
            args_type=MyToolArgsType,
            return_type=MyToolResponse,
            name=name,
            description=description,
        )

    async def run(
        self, args: MyToolArgsType, cancellation_token: CancellationToken
    ) -> MyToolResponse:
        """Execute the tool's functionality."""

        if not self.rbac_tool_helper.is_action_allowed(args.target_agent_id):
            raise PermissionError(f"Not allowed to target {args.target_agent_id}")

        request_message = MyToolRequest(
            content=args.task_description,
            sender=self.agent_id.key,
            target_agent_id=args.target_agent_id,
        )

        from runtime import get_runtime
        runtime = get_runtime()

        result: MyToolResponse = await runtime.send_message(
            request_message,
            recipient=AgentId(self.agent_id.type, args.target_agent_id),
            sender=self.agent_id,
        )

        return result
```

## Common Pitfalls

### 1. Missing Message Handlers

**Problem**: Tools send messages but recipients don't have corresponding handlers, causing silent failures or None responses.

**Solution**: Always implement `@message_handler` methods in recipient agents for each Request type your tool sends.

### 2. JSON Schema Requirements

**Problem**: Using `@dataclass` instead of `BaseModel` for ArgsType causes `model_json_schema` errors.

**Solution**: Always inherit ArgsType from `BaseModel`.

### 3. Message Type Mismatch

**Problem**: Sending messages that don't have corresponding handlers in the recipient agent.

**Solution**: Ensure the recipient agent has a `@message_handler` for your request type.

### 4. RBAC Policy Setup

**Problem**: Tools don't work because RBAC policies aren't properly configured.

**Solution**: Add appropriate `p` and `g` policies in `policy.csv` for the tool.

### 5. Circular Imports

**Problem**: Importing runtime modules at the top level can cause circular imports.

**Solution**: Import runtime modules inside methods where needed (see the `from runtime import get_runtime` pattern).

## Tool Registration

To make your tool available to agents:

1. Add your tool class to `ALL_TOOLS` in `tool_router.py`
2. Ensure proper RBAC policies are defined in `policy.csv`
3. The tool will automatically be available to agents with appropriate permissions

## Example: Adding Message Handler to VSMSystemAgent

Here's how to add a message handler for your tool to the `VSMSystemAgent` class:

```python
# In src/vsm_agent.py

@message_handler
async def handle_my_tool_request(
    self,
    message: MyToolRequest,
    ctx: CancellationToken,
) -> MyToolResponse:
    """Handle MyToolRequest messages."""
    print(f"[{self.agent_id.key}] Received MyToolRequest: {message.content}")

    # Process the request using the AssistantAgent
    result: TaskResult = await self._agent.run(
        task=message.content,
        cancellation_token=ctx.cancellation_token,
    )

    # Extract the response
    last_message = ""
    for result_message in result.messages:
        if isinstance(result_message, BaseChatMessage):
            print(f"[{self.agent_id.key}] {result_message.to_model_text()}")
            last_message = result_message.to_text()
        elif isinstance(result_message, BaseAgentEvent):
            print(f"[{self.agent_id.key}] {result_message.to_text()}")
            last_message = result_message.to_text()

    return MyToolResponse(content=last_message, success=True)
```

## Complete Workflow Example

### 1. Define Your Tool (in src/tools/my_tool.py)

```python
# Follow the template from the "Complete Example Template" section
```

### 2. Add to Tool Router (in src/tools/tool_router.py)

```python
from src.tools.my_tool import MyTool

ALL_TOOLS = [Delegate, Escalate, MyTool]  # Add your tool here
```

### 3. Add RBAC Policies (in src/rbac/policy.csv)

```csv
# Add policies for your tool
p, system3-control, MyTool, system1-operation
p, system5-policy, MyTool, *
```

### 4. Add Message Handler (in src/vsm_agent.py)

```python
# Add the @message_handler method as shown above
```

### 5. Test Your Tool

```python
# Test through the interactive interface or write unit tests
```

## Testing Your Tool

1. **Unit Testing**: Test the tool in isolation with mock arguments
2. **Integration Testing**: Test with the runtime and message handlers
3. **RBAC Testing**: Verify permissions work correctly
4. **End-to-End Testing**: Test through the full agent workflow

## Debugging Tips

- **Check RBAC logs**: Enable RBAC logging to see permission decisions
- **Inspect messages**: Add print statements to see message flow
- **Validate schemas**: Ensure your ArgsType has proper JSON schema generation
- **Test permissions**: Verify your agent has the right roles and policies
