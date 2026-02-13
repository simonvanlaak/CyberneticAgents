# scripts/issue_handlers/

Optional per-issue executors.

If present and executable, `../execute_issue.sh` will call:

- `scripts/issue_handlers/<ISSUE_NUMBER>.sh <repo> <issue_number>`

Use this when a specific issue can be implemented deterministically (e.g. a well-scoped mechanical change).

For most feature work (#5), the main agent will implement directly (tests-first, multiple atomic commits), and the cron worker will push once at the end.
