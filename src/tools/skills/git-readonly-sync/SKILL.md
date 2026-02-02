---
name: git-readonly-sync
description: Clone or pull public repositories in read-only workflows to gather reference material.
metadata:
  cyberagent:
    tool: exec
    subcommand: run
    timeout_class: standard
---

Use this skill to retrieve repository content for analysis without pushing changes.

Guidelines:
1. Only use read-only Git operations (`clone`, `fetch`, `pull`, `show`, `log`).
2. Do not commit, push, rebase, or rewrite history.
3. Prefer shallow clones for speed when full history is unnecessary.
4. Keep repository paths explicit in outputs.
