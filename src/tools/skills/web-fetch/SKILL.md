---
name: web-fetch
description: Fetch a single URL and extract readable article content for analysis and summarization.
metadata:
  cyberagent:
    tool: web_fetch
    subcommand: run
    timeout_class: standard
---

Use this skill when you already have a target URL and need clean readable text.

Guidelines:
1. Fetch one URL at a time.
2. Capture title, author/date when available, and main content.
3. Strip navigation/ads/noise before summarizing.
4. Flag paywalls, anti-bot blocks, or unavailable pages explicitly.
