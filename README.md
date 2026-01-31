# Cybernetic Agents

A general-purpose, adaptive framework for building self-organizing multi-agent systems based on cybernetic principles and Stafford Beer's Viable System Model (VSM). This system implements cybernetic control structures using **Microsoft AutoGen framework** with **Casbin RBAC** enforcement for secure, policy-driven agent coordination.

## Vision

Cybernetic Agents is designed to be a **domain-agnostic, self-adapting system** that implements organizational structures from management cybernetics as a living, breathing framework. Rather than requiring manual configuration for each use case, the system automatically develops specialized agents (experts) as needed, maintains organizational coherence through cybernetic feedback loops, and scales resources dynamically based on actual demand.

### Core Philosophy

- **Autopoiesis**: The system produces and maintains itself, creating new capabilities as needed
- **Requisite Variety**: The system's internal complexity matches the complexity of its environment
- **Recursive Structure**: Organizational patterns repeat at every level (agents contain agents)
- **Feedback-Driven Adaptation**: Continuous monitoring and adjustment based on performance and environmental changes

## Core Requirements

### 1. Domain Agnosticism

The system must operate effectively across any business domain without requiring domain-specific code changes:

- **Single Codebase**: All agents share the same runtime and AutoGen framework
- **Data-Driven Configuration**: Agent capabilities, system prompts, and behaviors defined via RBAC policies and configuration
- **Dynamic Capability Discovery**: The system learns what capabilities are needed through task patterns and environmental feedback
- **Adaptive System Prompts**: Each agent receives context-specific instructions, allowing specialization without code changes

### 2. Dynamic Growth and Shrinking

The system must automatically scale both horizontally (more agents) and vertically (new capabilities):

- **Automatic Agent Creation**: When a task requires a capability that doesn't exist, the system creates a new specialized agent on-demand via the factory pattern
- **Resource Optimization**: Agents are created/destroyed based on message flow
- **Capability Evolution**: Agents can be updated, merged, or retired based on usage patterns and effectiveness
- **Zero-Downtime Adaptation**: All changes occur without disrupting active tasks (AutoGen runtime handles lifecycle)

### 3. Cybernetic Control Structure

The system implements Stafford Beer's Viable System Model as its organizational backbone:

- **System 1 (Operations)**: Primary operational agents that execute tasks
- **System 2 (Coordination)**: Agents that coordinate between operational units
- **System 3 (Control)**: Agents that monitor and control operations (entry point)
- **System 4 (Intelligence)**: Agents that look outward, analyze the environment, and plan
- **System 5 (Policy)**: Agents that set policy and manage permissions

Each system level is recursive—agents at any level can contain sub-agents organized in the same structure.

### 4. Task Decision Framework

Every agent must be able to make one of four fundamental decisions when receiving a task:

- **RESPOND**: The agent can complete the task with its current capabilities
- **DELEGATE**: The agent breaks the task into subtasks and delegates to specialized agents
- **ESCALATE**: The agent cannot proceed and requires guidance from a higher-level system

**RBAC Enforcement**: All delegation and escalation decisions are enforced via Casbin policies. Agents can only communicate with other agents if permitted by the RBAC model.

### 5. Communication and Interoperability

The system uses standardized protocols for agent-to-agent communication:

- **AutoGen Messaging**: All agents communicate using AutoGen's pub-sub message protocol
- **Message Types**: Structured dataclass messages (`DelegateMessage`, `EscalateMessage`, `RespondMessage`)
- **Factory Pattern**: Agents created on-demand when first messaged
- **RBAC Enforcement**: Every message checked against Casbin policies before delivery

### 6. Memory and Learning

The system maintains both short-term and long-term memory:

- **Short-Term Memory**: Per-task conversation history maintained by AutoGen AssistantAgent
- **Long-Term Memory**: Future integration with vector databases for semantic retrieval
- **Cross-Agent Learning**: Agents can share insights through shared message context
- **Audit Trail**: RBAC enforcement logs all inter-agent communications

### 7. Security and Governance

The system enforces security and governance through RBAC policies:

- **Casbin RBAC**: Role-based access control with policy-as-code
- **Permission Model**: `(system_id, tool, parameter)` enforced on every message
- **Role Inheritance**: Agents inherit permissions from VSM system types
- **Privileged Operations**: Only System 5 can modify policies and create new agents
- **Secure Communication**: All inter-agent messages pass through RBAC enforcement layer
- **Auditability**: Every permission check is logged

## Current Implementation Architecture

### Technology Stack

- **Framework**: [AutoGen](https://microsoft.github.io/autogen/) (Microsoft) - Multi-agent orchestration
- **LLM**: [Groq](https://groq.com/) - llama-3.3-70b-versatile model
- **RBAC**: [Casbin](https://casbin.org/) - Policy-based access control
- **Database**: SQLite - Policy storage (`data/rbac.db`)
- **Language**: Python 3.12+

### System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      main.py (Entry Point)                   │
│  - Initializes runtime                                       │
│  - Registers agent factory                                   │
│  - Sends initial task to System 3                            │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                   RBACRuntime (Wrapper)                      │
│  - Wraps SingleThreadedAgentRuntime                          │
│  - Intercepts all send_message() calls                       │
│  - Enforces Casbin policies                                  │
│  - Logs permission decisions                                 │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│         SingleThreadedAgentRuntime (AutoGen Core)            │
│  - Manages agent lifecycle                                   │
│  - Routes messages via pub-sub                               │
│  - Creates agents on-demand via factory                      │
└────────────────────────┬─────────────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    ┌───────────┐  ┌───────────┐  ┌───────────┐
    │ System 5  │  │ System 3  │  │ System 1  │
    │  Policy   │  │  Control  │  │ Operations│
    │  Agent    │  │   Agent   │  │   Agent   │
    └───────────┘  └───────────┘  └───────────┘
    VSMSystemAgent (RoutedAgent wrapping AssistantAgent)
```

### Message Flow

```
1. User Request
   ↓
2. main.py creates DelegateMessage
   ↓
3. RBACRuntime.send_message()
   ├─ Extract: sender_id, recipient_id, message_type
   ├─ Map: DelegateMessage → "communication_delegate"
   ├─ Check: enforcer.enforce(sender, tool, recipient)
   ├─ Allow/Deny → Log decision
   └─ If allowed: forward to AutoGen runtime
       ↓
4. AutoGen Runtime
   ├─ Check: Does agent instance exist?
   ├─ If not: Call factory to create VSMSystemAgent
   └─ Route to: agent.handle_message()
       ↓
5. VSMSystemAgent.handle_message()
   ├─ Extract DelegateMessage content
   ├─ Call AssistantAgent.on_messages() → LLM
   ├─ LLM processes with system prompt
   └─ Return DelegateMessage response
       ↓
6. Response bubbles back to caller
```

## Getting Started

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/CyberneticAgents.git
cd CyberneticAgents

# Install dependencies
pip install autogen-agentchat autogen-ext casbin casbin-sqlalchemy-adapter python-dotenv

# Or install as package
pip install -e .
```

### Configuration

Create `.env` file or `src/.env`:
```bash
GROQ_API_KEY=your_groq_api_key_here
```

### Running the System

```bash
# Run with default task
python main.py
```

### Project Structure

```
CyberneticAgents/
├── main.py                         # Entry point (AutoGen-based)
├── .env                            # Environment variables
├── data/                           # Database files
│   └── rbac.db                     # Casbin RBAC policies (SQLite)
├── src/                            # Main source code
│   ├── agents/                     # Agent implementations
│   │   ├── __init__.py
│   │   └── vsm_agent.py            # VSMSystemAgent (RoutedAgent)
│   ├── rbac/                       # RBAC configuration
│   │   ├── enforcer.py             # Casbin enforcer
│   │   ├── model.conf              # RBAC model
│   │   └── policy.csv              # RBAC policies
│   ├── workbenches/                # AutoGen workbenches
│   │   ├── __init__.py
│   │   └── communication.py        # CommunicationWorkbench (WIP)
│   ├── prompts/                    # System-specific prompts
│   │   ├── root_control_sys3.txt
│   │   ├── root_operations_sys1.txt
│   │   ├── root_coordination_sys2.txt
│   │   ├── root_intelligence_sys4.txt
│   │   └── root_policy_sys5.txt
│   ├── tests/                      # Test suite
│   │   ├── __init__.py
│   │   └── test_rbac.py            # RBAC enforcement tests
│   ├── runtime.py                  # Runtime singleton manager
│   ├── rbac_runtime.py             # RBAC-wrapped runtime
│   ├── registry.py                 # Agent registration
│   └── README.md                   # Implementation TODO list
├── docs/                           # Documentation
│   ├── AutoGen/                    # AutoGen migration docs
│   ├── Multi Agent Systems/        # Research materials
│   ├── Prompt Engineering/         # Prompt best practices
│   └── Viable Systems Model/       # VSM theory
├── CLAUDE.md                       # Claude Code guidance
├── AGENT.md                        # AI assistant guidance
├── README.md                       # This file
└── pyproject.toml                  # Project configuration
```

### VSM System Hierarchy

The system implements five hierarchical levels based on Stafford Beer's VSM:

```
System 5 (Policy) - root_policy_sys5
  ├─ Manages RBAC policies and permissions
  ├─ Can delegate to: System 3, System 4
  ├─ Can modify: Casbin policies, agent creation rules
  └─ Ultimate authority in the system

System 4 (Intelligence) - root_intelligence_sys4
  ├─ Strategic planning and environmental analysis
  ├─ Can delegate to: System 3
  ├─ Can escalate to: System 5
  └─ Future-oriented thinking

System 3 (Control) - root_control_sys3
  ├─ Entry point for user requests
  ├─ Can delegate to: System 1, System 2
  ├─ Can escalate to: System 5
  ├─ Coordinates and monitors operations
  └─ **Default entry point** for all tasks

System 2 (Coordination) - root_coordination_sys2
  ├─ Mediates between operational units
  ├─ Can delegate to: System 1
  ├─ Can escalate to: System 3
  └─ Resolves conflicts between operations

System 1 (Operations) - root_operations_sys1
  ├─ Executes actual work
  ├─ Can escalate to: System 2, System 3
  └─ Primary work-performing agents
```

### RBAC Policy Model

RBAC policies are now defined programmatically in `src/tools/system_create.py`:

- **System 1 (Operations)**: Can escalate to System 2 and System 3
- **System 2 (Coordination)**: Can delegate to System 1, escalate to System 3
- **System 3 (Control)**: Can delegate to System 1 and System 2, escalate to System 5
- **System 4 (Intelligence)**: Can delegate to System 3, escalate to System 5
- **System 5 (Policy)**: Can delegate to System 3 and System 4, create new systems

**Adding a new agent**:
1. Use the SystemCreate tool to create the agent with automatic RBAC setup
2. Agent auto-created on first message

## Development Guide

### Running Tests

```bash
# Run RBAC enforcement tests
cd src
python tests/test_rbac.py

# Expected output:
# ✓ Test 1: Allowed delegation (user → sys3)
# ✓ Test 2: Blocked delegation (sys1 → sys3)
```

### Adding a New Agent

```python
# 1. Use SystemCreate tool (recommended):
from src.tools.system_create import create_system

# Creates system with automatic RBAC setup
create_system(namespace="myapp", system_type="operations", name="worker")

# 2. Send task (auto-creates agent)
from src.registry import send_task_to_agent

result = await send_task_to_agent(
    target_id="my_new_agent",
    task="Execute this task",
    source_id="user"
)
```

### Adding a New Message Type

```python
# 1. Define in src/agents/vsm_agent.py
@dataclass
class EscalateMessage:
    content: str
    sender: str
    recipient: str
    reason: str

# 2. Add handler
@message_handler
async def handle_escalate(
    self, message: EscalateMessage, ctx: MessageContext
) -> EscalateMessage:
    # Process escalation
    pass

# 3. Update RBAC mapping in src/rbac_runtime.py
tool_mapping = {
    "DelegateMessage": "communication_delegate",
    "EscalateMessage": "communication_escalate",
}

# 4. Export in src/agents/__init__.py
from .vsm_agent import VSMSystemAgent, DelegateMessage, EscalateMessage
```

### Code Quality Standards

**Type Hints** (Required):
```python
from typing import Optional

async def send_message(
    message: DelegateMessage,
    recipient: AgentId,
    timeout: Optional[int] = None
) -> DelegateMessage:
    pass
```

**Docstrings** (Required):
```python
async def register_vsm_agent_type() -> None:
    """
    Register the VSM agent type with the runtime.

    Creates a factory function that instantiates VSMSystemAgent
    instances on-demand when messages are first sent to them.
    """
    pass
```

**Import Organization**:
1. Standard library
2. Third-party (AutoGen, Casbin)
3. Local imports

```python
import os
from dataclasses import dataclass

from autogen_core import AgentId, RoutedAgent
from casbin import Enforcer

from src.runtime import get_runtime
```

## Current Status & Roadmap

### ✅ Implemented (Phase 1)

- [x] AutoGen Core Runtime integration
- [x] RBAC enforcement with Casbin
- [x] Factory-based agent creation
- [x] VSM hierarchy (5 system levels)
- [x] DelegateMessage type
- [x] Permission logging and audit
- [x] On-demand agent instantiation
- [x] Basic testing infrastructure

### ⏳ In Progress (Phase 2)

- [ ] EscalateMessage and RespondMessage types
- [ ] Complete CommunicationWorkbench implementation
- [ ] Dynamic system prompt loading from database
- [ ] Tool integration via workbench
- [ ] Enhanced testing (unit + integration)

### 📋 Planned (Phase 3+)

- [ ] Recursive VSM structure (agents within agents)
- [ ] Learning and optimization capabilities
- [ ] Multi-model support (beyond Groq)
- [ ] Distributed runtime (multi-node)
- [ ] Vector database integration for long-term memory
- [ ] Agent performance metrics
- [ ] Self-healing and recovery mechanisms
- [ ] Web UI for monitoring and control

## Documentation

### Core Concepts

- **[CLAUDE.md](./CLAUDE.md)** - Guidance for Claude Code
- **[AGENT.md](./AGENT.md)** - Guidance for AI coding assistants
- **[Viable Systems Model](./docs/Viable%20Systems%20Model/)** - VSM theory and application
- **[Multi-Agent Systems](./docs/Multi%20Agent%20Systems/)** - Multi-agent architecture patterns
- **[AutoGen Migration](./docs/AutoGen/)** - AutoGen integration details

### API Documentation

See inline docstrings in source code:
- `src/runtime.py` - Runtime management
- `src/rbac_runtime.py` - RBAC enforcement
- `src/registry.py` - Agent registration
- `src/agents/vsm_agent.py` - Agent implementation

## Contributing

Contributions that enhance the cybernetic, self-organizing nature of the system are welcome:

- **Domain agnosticism** - Making the system work across more domains
- **Dynamic adaptation** - Improving self-organization capabilities
- **VSM implementation** - Better alignment with cybernetic principles
- **RBAC policies** - More sophisticated permission models
- **Testing** - Expanding test coverage

**Contribution Guidelines**:
- Follow code quality standards (type hints, docstrings)
- Add tests for new functionality
- Update documentation as needed
- Keep PRs focused on single improvements
- Ensure RBAC policies are correct

## License

[To be determined]

---

**Built with**:
- [AutoGen](https://microsoft.github.io/autogen/) by Microsoft
- [Casbin](https://casbin.org/) for RBAC
- [Groq](https://groq.com/) for LLM inference
- [Stafford Beer's](https://en.wikipedia.org/wiki/Stafford_Beer) Viable System Model
