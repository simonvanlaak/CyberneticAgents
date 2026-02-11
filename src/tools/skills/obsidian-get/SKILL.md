---
name: obsidian-get
description: Read a specific note from an Obsidian vault and return the full markdown content.
metadata:
  cyberagent:
    tool: obsidian-get
    timeout_class: standard
input_schema:
  type: object
  properties:
    path:
      type: string
      description: Relative path within the vault (e.g. "Projects/Plan.md").
    max_chars:
      type: integer
      description: Max characters to return (default 20000).
output_schema:
  type: object
  properties:
    path:
      type: string
    content:
      type: string
    truncated:
      type: boolean
    error:
      type: string
---

Use this skill to load the full text of a note after you have identified it (for example via `obsidian-search`).

Safety:
- The provided `path` is resolved relative to `OBSIDIAN_VAULT_PATH` and must stay within the vault.
