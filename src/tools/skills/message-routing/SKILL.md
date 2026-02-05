---
name: message-routing
description: Create, update, and inspect message routing rules and dead-letter queues.
metadata:
  cyberagent:
    tool: message-routing
    subcommand: run
    timeout_class: standard
input_schema:
  type: object
  properties:
    action:
      type: string
      description: create_rule, disable_rule, list_rules, list_dlq
    team_id:
      type: integer
    rule_id:
      type: integer
    name:
      type: string
    channel:
      type: string
    filters:
      type: string
      description: JSON object of exact-match filters.
    targets:
      type: string
      description: JSON array of targets.
    priority:
      type: integer
    active:
      type: boolean
    status:
      type: string
output_schema:
  type: object
  properties:
    result:
      type: object
    error:
      type: string
---

Use this skill to manage message routing rules and inspect dead-letter queues.

Notes:
1. Filters and targets must be JSON strings.
2. Matching is exact in v1.
