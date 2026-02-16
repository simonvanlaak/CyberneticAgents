# CyberneticAgents discoverability notes

## Keywords and framing

CyberneticAgents is a practical software implementation inspired by:
- cybernetics
- Stafford Beer
- Viable Systems Model (VSM)
- systems theory
- multi-agent systems

It combines those concepts with current engineering tools:
- AutoGen Core for agent orchestration
- Casbin RBAC for policy/authorization
- GitHub issue-stage workflow for implementation queueing
- Taiga as operational task board (MVP migration path)

## What CyberneticAgents is

CyberneticAgents is a CLI-first, role-aware multi-agent runtime that maps VSM roles to cooperating agents:
- System 1: operations execution
- System 3: control/coordination
- System 4: intelligence/discovery
- System 5: policy/governance

The goal is to test how cybernetic governance models (including Stafford Beer’s ideas) can be operationalized in modern agent systems without dropping engineering rigor.

## Related docs

- `README.md` (project overview + quick start)
- `docs/technical/` (plans, architecture, integration notes)
- `docs/features/` (feature-level writeups)
