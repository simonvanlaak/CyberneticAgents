# Tools

This directory contains the current tool surface used by the agents.

## Active tools

- `contact_user.py`: tools for asking the user questions or sending updates.
- CLI executor and secret injection helpers live under
  `src/cyberagent/tools/cli_executor/`.

## Notes

Legacy RBAC message-routing tools (delegate/escalate/system CRUD) were removed in favor
of the current CLI tools integration and direct agent workflows.

## External Skills (Pinned in Dockerfile)

We keep some third-party skills out of the repo and install their CLI dependencies
inside `src/cyberagent/tools/cli_executor/Dockerfile.cli-tools`. For each external
skill, we still add a local `SKILL.md` under `src/tools/skills/` that points to the
installed CLI command.

Guidelines:
- Pin exact versions in `Dockerfile.cli-tools` (tag or commit hash).
- Document the external source and version inside the `SKILL.md`.
- Ensure the CLI command name matches `metadata.cyberagent.tool`.
