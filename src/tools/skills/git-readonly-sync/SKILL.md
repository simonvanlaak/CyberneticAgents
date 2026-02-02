---
name: git-readonly-sync
description: Clone or pull public repositories in read-only workflows to gather reference material.
metadata:
  cyberagent:
    tool: git-readonly-sync
    timeout_class: standard
input_schema:
  type: object
  properties:
    repo:
      type: string
    dest:
      type: string
    branch:
      type: string
    depth:
      type: integer
    token_env:
      type: string
    token_username:
      type: string
output_schema:
  type: object
  properties:
    output:
      type: string
    error:
      type: string
---

Use this skill to retrieve repository content for analysis without pushing changes.

Guidelines:
1. Only use read-only Git operations (`clone`, `fetch`, `pull`, `show`, `log`).
2. Do not commit, push, rebase, or rewrite history.
3. Prefer shallow clones for speed when full history is unnecessary.
4. Keep repository paths explicit in outputs.

Inputs (CLI args):
- `--repo`: repository URL (https or ssh).
- `--dest`: destination directory.
- `--branch`: branch name (default: main).
- `--depth`: shallow clone depth (default: 1).
- `--token-env`: env var name containing a read-only token (optional).
- `--token-username`: username for the token (optional, defaults to x-access-token).

Notes:
- For private repos, provide `--token-env` and ensure the token is supplied via 1Password.
