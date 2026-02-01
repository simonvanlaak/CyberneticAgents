# Tools

This directory contains the current tool surface used by the agents.

## Active tools

- `contact_user.py`: tools for asking the user questions or sending updates.
- OpenClaw CLI executor and secret injection helpers live under
  `src/cyberagent/tools/cli_executor/`.

## Notes

Legacy RBAC message-routing tools (delegate/escalate/system CRUD) were removed in favor
of the current OpenClaw integration and direct agent workflows.
