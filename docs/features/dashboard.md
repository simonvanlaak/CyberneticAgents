# Dashboard Feature

## Overview
The dashboard is a local read-only Streamlit UI for viewing operational state.
It provides Kanban and team views, plus task drill-down details, without
mutating runtime data.

## Core Capabilities
- **Kanban board**: Groups tasks by team/purpose/strategy/initiative and status.
- **Task filters**: Filter by team, strategy, initiative, and assignee.
- **Task details page**: Click a task card to open a dedicated detail page.
- **Case judgement visibility**: Shows persisted policy review case judgements per task.
- **Teams page**: Shows teams, members, and their policy/permission summaries.
- **Log badge**: Displays warning/error counts from the latest runtime log file.

## UI Pages
- `Kanban`: Main task board and task table.
- `Teams`: Team and member overview.
- `Task Details`: Selected task metadata, content, result, and case judgement.

## Runtime Behavior
- `cyberagent dashboard` starts Streamlit for `src/cyberagent/ui/dashboard.py`.
- The CLI prefers the current Python interpreter; if Streamlit is missing there,
  it falls back to repo-local `.venv/bin/python` when available.
- If Streamlit is unavailable in both locations, the CLI exits with a clear
  install instruction.

## Data Model Notes
- Task cards are read from SQLite with hierarchy joins.
- Task detail includes:
  - `id`, `status`, `assignee`, `name`, `content`, `result`
  - team/purpose/strategy/initiative identifiers and names
  - `case_judgement` (JSON payload persisted from System3 policy review)

## How to Test
- `python3 -m pytest tests/cli/test_dashboard_command.py -q`
- `python3 -m pytest tests/cyberagent/test_kanban_data.py -q`
- `python3 -m pytest tests/cyberagent/test_dashboard_log_badge.py -q`

## File Map
- `src/cyberagent/ui/dashboard.py`
- `src/cyberagent/ui/kanban_data.py`
- `src/cyberagent/cli/cyberagent.py`
- `tests/cli/test_dashboard_command.py`
- `tests/cyberagent/test_kanban_data.py`
- `tests/cyberagent/test_dashboard_log_badge.py`
