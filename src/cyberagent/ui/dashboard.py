from __future__ import annotations

import importlib
from typing import Any

try:
    from src.cyberagent.ui.kanban_data import (
        KANBAN_STATUSES,
        group_tasks_by_hierarchy,
        load_task_cards,
    )
    from src.cyberagent.ui.teams_data import load_teams_with_members
    from src.cyberagent.ui.dashboard_log_badge import count_warnings_errors
    from src.cyberagent.core.paths import get_logs_dir
except ModuleNotFoundError:
    from kanban_data import (
        KANBAN_STATUSES,
        group_tasks_by_hierarchy,
        load_task_cards,
    )
    from teams_data import load_teams_with_members
    from dashboard_log_badge import count_warnings_errors
    from src.cyberagent.core.paths import get_logs_dir


def _load_streamlit() -> Any:
    try:
        return importlib.import_module("streamlit")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Streamlit is not installed. Add 'streamlit' to dependencies and install."
        ) from exc


def _apply_filters(
    tasks: list[Any], st: Any
) -> tuple[int | None, int | None, int | None, str | None]:
    team_options = sorted(
        {(task.team_id, task.team_name) for task in tasks}, key=lambda item: item[1]
    )
    team_choice = st.sidebar.selectbox(
        "Team",
        options=[None] + team_options,
        format_func=lambda item: (
            "All teams" if item is None else f"{item[1]} ({item[0]})"
        ),
    )
    team_id = team_choice[0] if team_choice else None

    strategy_options = sorted(
        {
            (task.strategy_id, task.strategy_name)
            for task in tasks
            if task.strategy_id is not None and task.strategy_name is not None
        },
        key=lambda item: item[1],
    )
    strategy_choice = st.sidebar.selectbox(
        "Strategy",
        options=[None] + strategy_options,
        format_func=lambda item: (
            "All strategies" if item is None else f"{item[1]} ({item[0]})"
        ),
    )
    strategy_id = strategy_choice[0] if strategy_choice else None

    initiative_options = sorted(
        {
            (task.initiative_id, task.initiative_name)
            for task in tasks
            if task.initiative_id is not None and task.initiative_name is not None
        },
        key=lambda item: item[1],
    )
    initiative_choice = st.sidebar.selectbox(
        "Initiative",
        options=[None] + initiative_options,
        format_func=lambda item: (
            "All initiatives" if item is None else f"{item[1]} ({item[0]})"
        ),
    )
    initiative_id = initiative_choice[0] if initiative_choice else None

    assignee_options = sorted({task.assignee for task in tasks if task.assignee})
    assignee = st.sidebar.selectbox(
        "Assignee",
        options=[None] + assignee_options,
        format_func=lambda value: "All assignees" if value is None else value,
    )
    return team_id, strategy_id, initiative_id, assignee


def render_board() -> None:
    st = _load_streamlit()
    st.set_page_config(page_title="CyberneticAgents Kanban", layout="wide")

    warnings, errors = count_warnings_errors(get_logs_dir())
    title_col, badge_col = st.columns([8, 2])
    with badge_col:
        st.markdown(f"⚠️ **{warnings}**  ❌ **{errors}**")

    page = st.sidebar.selectbox("Page", ["Kanban", "Teams"])
    if page == "Teams":
        with title_col:
            st.title("CyberneticAgents Teams (Read-Only)")
        render_teams_page(st)
        return

    with title_col:
        st.title("CyberneticAgents Task Kanban (Read-Only)")

    all_tasks = load_task_cards()
    if not all_tasks:
        st.info("No tasks found.")
        return

    team_id, strategy_id, initiative_id, assignee = _apply_filters(all_tasks, st)
    filtered_tasks = load_task_cards(
        team_id=team_id,
        strategy_id=strategy_id,
        initiative_id=initiative_id,
        assignee=assignee,
    )
    hierarchy_rows = group_tasks_by_hierarchy(filtered_tasks)
    for row in hierarchy_rows:
        purpose_text = row.purpose_name or "-"
        strategy_text = row.strategy_name or "-"
        initiative_text = row.initiative_name or "-"
        st.subheader(
            f"Team {row.team_name} ({row.team_id}) · "
            f"Purpose {purpose_text} · Strategy {strategy_text} · "
            f"Initiative {initiative_text} ({row.initiative_id})"
        )
        columns = st.columns(len(KANBAN_STATUSES))
        for idx, status in enumerate(KANBAN_STATUSES):
            column = columns[idx]
            cards = row.tasks_by_status[status]
            column.markdown(f"**{status} ({len(cards)})**")
            if not cards:
                column.caption("No tasks")
                continue
            for task in cards:
                assignee_text = task.assignee or "-"
                column.markdown(
                    "\n".join(
                        [
                            f"**#{task.id} {task.name}**",
                            f"- Assignee: `{assignee_text}`",
                        ]
                    )
                )
                column.divider()

    st.subheader("Task Table")
    st.dataframe(
        [
            {
                "id": task.id,
                "status": task.status,
                "assignee": task.assignee,
                "name": task.name,
                "team": task.team_name,
                "purpose": task.purpose_name,
                "strategy": task.strategy_name,
                "initiative": task.initiative_name,
            }
            for task in filtered_tasks
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_teams_page(st: Any) -> None:
    teams = load_teams_with_members()
    if not teams:
        st.info("No teams found.")
        return

    for team in teams:
        st.subheader(f"Team {team.team_name} ({team.team_id})")
        team_policies_text = ", ".join(team.policies) if team.policies else "-"
        team_permissions_text = ", ".join(team.permissions) if team.permissions else "-"
        st.caption(f"Team policies: {team_policies_text}")
        st.caption(f"Team permissions: {team_permissions_text}")
        if not team.members:
            st.caption("No team members")
            continue
        st.dataframe(
            [
                {
                    "id": member.id,
                    "name": member.name,
                    "type": member.system_type,
                    "agent_id": member.agent_id_str,
                    "system_policies": (
                        ", ".join(member.policies) if member.policies else "-"
                    ),
                    "system_permissions": (
                        ", ".join(member.permissions) if member.permissions else "-"
                    ),
                }
                for member in team.members
            ],
            use_container_width=True,
            hide_index=True,
        )


def main() -> None:
    render_board()


if __name__ == "__main__":
    main()
