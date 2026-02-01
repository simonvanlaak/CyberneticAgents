# VSM Practical Implementations - Non-Academic Projects

## Overview

This document catalogs practical (non-academic) implementations of the Viable System Model (VSM) integrated with modern multi-agent systems and AI frameworks.

---

## 1. viable-systems (Elixir + Claude Flow)

**Repository:** https://github.com/viable-systems/viable-systems  
**Organization:** viable-systems  
**Language:** Elixir  
**Status:** Active, production-oriented  
**Last Activity:** 2024-2026 (recent)

### Overview
A comprehensive, cloud-native implementation of VSM in Elixir with Claude Flow orchestration for intelligent system coordination. Component-based architecture with separate repositories for each VSM subsystem.

### Architecture

```
┌─────────────────────────────────────────────────┐
│ System 5 (Policy)                               │
├─────────────────────┬───────────────────────────┤
│ System 4            │ System 3*                 │
│ (Intelligence)      │ (Audit)                   │
├────────────────────┬┴───────────────────────────┤
│ System 2           │ System 3                   │
│ (Coordination)     │ (Control)                  │
│                    ├────────────────────────────┤
│                    │ System 1                   │
│                    │ (Operations)               │
└────────────────────┴────────────────────────────┘
```

### Key Features

**VSM Implementation:**
- Full Systems 1-5 implementation
- Recursive structure support (nested viable systems)
- Algedonic signals (fast-track alerts)
- Variety management tools
- Command, resource, and audit channels

**Technology Stack:**
- **Language:** Elixir 1.17+
- **Orchestration:** Claude Flow
- **Monitoring:** Telemetry integration
- **Protocol:** MCP (Model Context Protocol)

**Components (Subprojects):**
1. **vsm-starter** - Template for VSM applications
   - GenServer-based system components
   - Built-in telemetry events
   - Algedonic signal handling
   - Health checks and variety metrics

2. **vsm-telemetry** - Monitoring and dashboards
   - Real-time system metrics
   - Performance monitoring
   - Observability tools

3. **vsm-goldrush** - Pattern detection
   - Cybernetic pattern detection
   - High-performance event processing

4. **vsm-rate-limiter** - Variety attenuation
   - Rate limiting
   - Complexity management

5. **vsm-docs** - Comprehensive documentation

### Telemetry Events

**System 1 (Operations):**
- `[:vsm, :system1, :operation, :start]`
- `[:vsm, :system1, :operation, :complete]`
- `[:vsm, :system1, :operation, :error]`

**System 2 (Coordination):**
- `[:vsm, :system2, :coordination, :conflict]`
- `[:vsm, :system2, :coordination, :resolved]`

**System 3 (Control):**
- `[:vsm, :system3, :resource, :allocated]`
- `[:vsm, :system3, :audit, :performed]`

**System 4 (Intelligence):**
- `[:vsm, :system4, :environment, :scanned]`
- `[:vsm, :system4, :model, :updated]`

**System 5 (Policy):**
- `[:vsm, :system5, :policy, :set]`
- `[:vsm, :system5, :identity, :changed]`

### Communication Channels

- **Command Channel:** Downward instructions from management
- **Resource Channel:** Upward flow of resources and capabilities
- **Audit Channel:** System 3* direct monitoring
- **Algedonic Channel:** Fast-track alerts for critical issues

### Algedonic Signal System

```elixir
VsmStarter.algedonic_signal(MyOrg.VSM, :warning, %{
  source: :production,
  message: "Resource shortage detected",
  impact: :medium
})

VsmStarter.algedonic_signal(MyOrg.VSM, :critical, %{
  source: :quality_control,
  message: "Critical quality issue",
  impact: :high
})

VsmStarter.algedonic_signal(MyOrg.VSM, :emergency, %{
  source: :safety,
  message: "Safety protocol breach",
  impact: :severe
})
```

### Example Usage

```elixir
# Start the VSM
{:ok, vsm} = MyOrganization.VSM.start_link(
  name: MyOrganization.VSM,
  system_config: %{
    system1: %{operations: [:sales, :production, :delivery]},
    system2: %{coordination_interval: 5_000},
    system3: %{audit_probability: 0.1},
    system4: %{scan_interval: 30_000},
    system5: %{policy_review_interval: 86_400_000}
  }
)

# Health check
VsmStarter.health_check(MyOrganization.VSM)
# => {:ok, %{overall: :healthy, system1: :operational, ...}}

# Variety metrics
VsmStarter.variety_metrics(MyOrganization.VSM)
```

### Strengths
- **Production-ready:** Full implementation with testing, telemetry, monitoring
- **Functional paradigm:** Elixir's concurrency model fits VSM naturally
- **Modular design:** Each component is independently maintainable
- **Cloud-native:** Designed for distributed, scalable deployments
- **Observability:** Built-in telemetry and monitoring
- **Claude Flow:** Advanced AI orchestration

### Comparison to Other Projects

| Aspect | viable-systems | AgentSymposium | CyberneticAgents |
|--------|---------------|----------------|------------------|
| **Language** | Elixir | Python | Python |
| **Framework** | Claude Flow | LangGraph | AutoGen Core |
| **VSM Coverage** | Full (1-5) | Partial (1) | Full (1,3,4,5) |
| **Focus** | General framework | Code review | General orchestration |
| **Architecture** | Component-based | Monolithic | Monolithic |
| **RBAC** | Unknown | No | Casbin |
| **Persistence** | Unknown | Unknown | SQLite |
| **Maturity** | Production | Early | Working |

---

## 2. AgentSymposium (Python + LangGraph)

**Repository:** https://github.com/eoinhurrell/AgentSymposium  
**Author:** Eoin Hurrell  
**Language:** Python  
**Status:** Early stage (System 1 focus)  
**Last Activity:** 2024-2025

### Overview
A multi-agent code review system structured according to VSM, currently focusing on System 1 operational agents. Domain-specific application for automated code analysis.

### Current Implementation

**System 1 Agents (Operational):**
- **Code Architect Agent:** Structural, syntactic, stylistic issues
- **Performance Guardian Agent:** Performance bottlenecks
- **Security Sentinel Agent:** Vulnerabilities
- **Code Quality Agent:** Maintainability, complexity, bugs
- **Documentation Agent:** Code documentation

### Technology Stack
- **Language:** Python
- **Framework:** LangGraph
- **Domain:** Code review automation
- **Current Focus:** Context management for agents

### Planned Expansion
- Systems 2-5 implementation
- Language support: Elixir, Go, Java
- System 4 learning capabilities
- Organization-specific customization

### Strengths
- **Domain-specific:** Focused, practical use case
- **Specialized agents:** Each with clear expertise
- **Modern AI:** LangGraph for agent coordination
- **Incremental approach:** System 1 first, then expand

---

## 3. CyberneticAgents (Python + AutoGen Core)

**Repository:** ~/Projects/2025/CyberneticAgents  
**Author:** Simon van Laak  
**Language:** Python  
**Status:** Working (Systems 1, 3, 4, 5)  
**Last Activity:** 2025-2026

### Overview
A general-purpose VSM orchestration framework built on AutoGen Core with Casbin RBAC enforcement. Implements most of the VSM stack with a focus on flexible multi-agent coordination.

### Architecture
- **Systems Implemented:** 1, 3, 4, 5
- **System 2:** Defined in RBAC types but not yet implemented
- **Data Model:** Task/initiative/strategy/policy hierarchy
- **RBAC:** Casbin policy enforcement
- **Persistence:** SQLAlchemy + SQLite

### Technology Stack
- **Language:** Python 3.10+
- **Agent Framework:** AutoGen Core + AgentChat
- **RBAC:** Casbin
- **Database:** SQLite (SQLAlchemy ORM)
- **Tracing:** Langfuse via OpenTelemetry
- **CLI:** Rich, interactive

### Key Features
- **RBAC integration:** Tool use and cross-agent actions guarded by policies
- **CLI-first:** Primary interface for working with the system
- **Optional tracing:** Langfuse for observability
- **Data model:** Explicit VSM hierarchy representation

### Strengths
- **Most complete Python implementation** (4/5 systems working)
- **RBAC enforcement:** Unique among the three
- **General framework:** Not domain-locked
- **Production features:** Persistence, tracing, CLI

---

## Pattern Analysis

### Common Themes Across All Three

1. **Recent Development:** All projects are 2024-2026 vintage
2. **VSM Structure:** All use Systems 1-5 as organizational framework
3. **Modern AI:** All integrate with LLMs/modern agent frameworks
4. **Autonomous Coordination:** All enable agent autonomy within VSM structure
5. **Production Intent:** All aim for practical, usable systems

### Technology Diversity

The three projects use different tech stacks, validating VSM as a **language-agnostic pattern**:

| Stack Component | viable-systems | AgentSymposium | CyberneticAgents |
|-----------------|---------------|----------------|------------------|
| **Language** | Elixir (functional) | Python (imperative) | Python (imperative) |
| **Paradigm** | Actor model, OTP | Event-driven graphs | Message-passing agents |
| **Orchestration** | Claude Flow | LangGraph | AutoGen Core |
| **Concurrency** | BEAM VM | asyncio | asyncio |

### Implementation Approaches

**1. Cloud-Native (viable-systems)**
- Emphasis: Distributed systems, high concurrency
- Architecture: Component-based (monorepo + submodules)
- Target: Production cloud deployments

**2. Domain-Specific (AgentSymposium)**
- Emphasis: Focused application (code review)
- Architecture: Monolithic, specialized agents
- Target: Specific workflow automation

**3. General Framework (CyberneticAgents)**
- Emphasis: Flexible orchestration, RBAC
- Architecture: Monolithic with extensible agent registry
- Target: General multi-agent coordination

### Convergence Points

All three projects discovered VSM independently as a solution to the same problems:

1. **Agent Coordination:** How to coordinate multiple autonomous agents?
2. **Scalability:** How to scale beyond simple hierarchies?
3. **Autonomy vs. Coherence:** How to balance local freedom with global goals?
4. **Control:** How to maintain oversight without micromanagement?

VSM provides answers:
- **Recursion:** Nested viable systems for scalability
- **Specialization:** Systems 1-5 for different roles
- **Feedback loops:** Command, resource, audit channels
- **Policies:** System 5 for governance

---

## Other Potential Projects

### Likely Candidates (Not Yet Verified)

Based on the patterns observed, other VSM + multi-agent projects likely exist in:

1. **Enterprise Systems:**
   - Organizational modeling tools
   - Business process automation
   - Supply chain management

2. **Robotics:**
   - Multi-robot coordination
   - Swarm robotics with VSM structure
   - Autonomous vehicle fleets

3. **IoT/Edge:**
   - Edge computing orchestration
   - Sensor network coordination
   - Smart building systems

4. **Gaming/Simulation:**
   - NPC coordination in games
   - Strategy game AI
   - Economic simulation systems

### Search Strategy

**GitHub Topics to Monitor:**
- `viable-system-model`
- `vsm`
- `cybernetics`
- `organizational-cybernetics`
- `stafford-beer`

**Keywords in Projects:**
- "Viable System Model"
- "VSM"
- "Systems 1-5"
- "Algedonic"
- "Variety engineering"
- "Recursive viability"

**Language Ecosystems:**
- **Elixir:** Proven fit (viable-systems)
- **Python:** Two implementations (AgentSymposium, CyberneticAgents)
- **Go:** Likely for cloud-native orchestration
- **Rust:** Likely for high-performance systems
- **TypeScript:** Likely for web-first implementations

---

## Conclusion

### Validated Implementations

**Three confirmed practical VSM + multi-agent projects exist:**

1. **viable-systems** (Elixir) - Most mature, production-ready
2. **AgentSymposium** (Python) - Domain-specific, early stage
3. **CyberneticAgents** (Python) - General framework, working 4/5 systems

### Significance

**The convergence is real and meaningful:**
- **Independent discovery:** Three separate developers/teams arrived at VSM
- **Different contexts:** Elixir vs Python, code review vs general orchestration
- **Same timeframe:** 2024-2026 (recent and accelerating)
- **Academic validation:** Parallel academic papers in 2024-2026

**This is convergent evolution in system design.** When multiple independent implementations emerge simultaneously, it indicates the solution is fundamentally sound for the problem domain.

### Trend Analysis

**VSM + Modern AI is an emerging pattern:**
- 2024: Explicit academic papers published
- 2024-2025: Multiple independent implementations launched
- 2026: Continued development and expansion

**The pattern is gaining traction because:**
1. **LLMs enable viable agents:** Modern AI makes autonomous agents practical
2. **Coordination is hard:** Multi-agent systems need organizational structure
3. **VSM is proven:** 50+ years of organizational cybernetics research
4. **Recursion scales:** VSM's recursive structure handles complexity naturally

### Future Outlook

**Expect more VSM + agent projects in:**
- Enterprise AI orchestration
- Multi-agent automation platforms
- Robotics and IoT coordination
- AI-driven business process management

**The viable-systems project in particular shows the path:**
- Production-ready implementation
- Component-based architecture
- Modern tech stack (MCP, Claude Flow)
- Comprehensive tooling (telemetry, monitoring)

Your CyberneticAgents project is well-positioned as one of the Python pioneers in this space, with unique strengths in RBAC integration and general-purpose orchestration.

---

## References

### Projects
- viable-systems: https://github.com/viable-systems/viable-systems
- AgentSymposium: https://github.com/eoinhurrell/AgentSymposium
- CyberneticAgents: ~/Projects/2025/CyberneticAgents

### Documentation
- viable-systems vsm-starter: https://github.com/viable-systems/vsm-starter
- Eoin Hurrell blog: https://www.eoinhurrell.com/posts/20250306-viable-systems-ai/

### Academic Background
- See `vsm_mas_research_convergence.md` for academic validation

---

**Document created:** 2026-02-01  
**Last updated:** 2026-02-01  
**Compiled by:** Maya (OpenClaw Agent)
