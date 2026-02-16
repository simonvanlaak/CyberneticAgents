# Dashboard Feature

## Overview
The dashboard is a local read-only Streamlit UI for operational visibility
outside of task-board management.

Task-board operations now live in **Taiga UI** and are opened via:

```bash
cyberagent kanban
```

## Core Capabilities
- **Teams page**: Shows teams, members, and their policy/permission summaries.
- **Inbox page**: Shows user prompts, system questions/responses, and supports
  answering pending questions.
- **Memory page**: Shows searchable/paginated memory entries.
- **Log badge**: Displays warning/error counts from runtime logs.

## UI Pages
- `Teams`: Team and member overview.
- `Inbox`: Message and pending-question visibility.
- `Memory`: Memory inspection and filtering.

## Runtime Behavior
- `cyberagent dashboard` starts Streamlit for `src/cyberagent/ui/dashboard.py`.
- The CLI prefers the current Python interpreter; if Streamlit is missing there,
  it falls back to repo-local `.venv/bin/python` when available.
- If Streamlit is unavailable in both locations, the CLI exits with a clear
  install instruction.
- `cyberagent kanban` opens (or prints) the Taiga UI URL.

## How to Test
- `python3 -m pytest tests/cli/test_dashboard_command.py -q`
- `python3 -m pytest tests/cli/test_kanban_command.py -q`
- `python3 -m pytest tests/cyberagent/test_dashboard_ui.py -q`
- `python3 -m pytest tests/cyberagent/test_dashboard_log_badge.py -q`

## File Map
- `src/cyberagent/ui/dashboard.py`
- `src/cyberagent/cli/cyberagent.py`
- `src/cyberagent/cli/kanban.py`
- `tests/cli/test_dashboard_command.py`
- `tests/cli/test_kanban_command.py`
- `tests/cyberagent/test_dashboard_ui.py`
- `tests/cyberagent/test_dashboard_log_badge.py`
