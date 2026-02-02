---
name: web-search
description: Search the public web for current information and return concise source-backed findings.
metadata:
  cyberagent:
    tool: web_search
    subcommand: run
    timeout_class: standard
    required_env:
      - BRAVE_API_KEY
input_schema:
  type: object
  properties:
    query:
      type: string
    count:
      type: integer
    offset:
      type: integer
    freshness:
      type: string
output_schema:
  type: object
  properties:
    results:
      type: array
    error:
      type: string
---

Use this skill when you need web search results for recent events, niche topics, or source discovery.

Guidelines:
1. Build precise queries with clear entities, dates, and constraints.
2. Prefer official/primary sources when available.
3. Summarize key findings with short citations.
4. If no strong sources are found, report uncertainty and suggest next queries.
