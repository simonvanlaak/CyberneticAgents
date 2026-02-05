# Message Routing

## Overview
Message routing determines which system or subteam receives inbound user messages.
Routing rules are stored per team and evaluated top-down through the recursion
hierarchy. Each team can route to its own System1 agents or to subteams. If no
rule matches (or no targets resolve), the message is placed in a dead-letter
queue (DLQ) and routed to that team's System4 by default.

## Routing Rules
Rules are stored in `routing_rules` and include:
- `team_id`: Team that owns the rule.
- `name`: Human-readable rule name.
- `channel`: Channel name (e.g. `cli`, `telegram`, or `*`).
- `filters_json`: Exact-match metadata filters (key/value pairs).
- `targets_json`: List of targets.
- `priority`: Higher priority wins (sorted DESC, tie by id ASC).
- `active`: Whether the rule is enabled.
- `created_by_system_id` / `updated_by_system_id`.

### Filters
Filters match exact values on the routing context metadata. Example keys:
- `sender_id`
- `session_id`

The `channel` can be matched via the rule's `channel` field or as a metadata
filter.

### Targets
Targets are a list of objects with one of the following keys:
- `system_id`: numeric system id or agent id string.
- `team_id`: subteam id (recurses into that team's routing rules).

Multiple targets are allowed. Each target expands into one or more agent ids.

## Routing Flow
1. A message arrives at the root team.
2. The root team evaluates its routing rules (exact match).
3. Targets are resolved:
   - `system_id` routes directly to that agent.
   - `team_id` recurses into the subteam and repeats routing.
4. If no rule matches or no targets resolve, a DLQ entry is created and the
   message is routed to the team's System4.

## Defaults
Default routing rules live in team config and are seeded during onboarding.
Example (`config/defaults/teams/root_team.json`):
```json
"routing_rules": [
  {
    "name": "default-dlq",
    "channel": "*",
    "filters": {},
    "targets": [
      {"system_id": "System4/root"}
    ],
    "priority": 0,
    "active": true
  }
]
```

## Skill: message-routing
The `message-routing` skill manages routing rules and the DLQ.
Available actions:
- `create_rule`
- `update_rule`
- `disable_rule`
- `list_rules`
- `list_dlq`

Rules can be added by SOPs during onboarding by defining routing rules in the
procedure payload. These rules are seeded when the SOP is loaded.
