from __future__ import annotations

import importlib
import json
import os
from typing import Any

try:
    from src.cyberagent.ui.kanban_data import (
        KANBAN_STATUSES,
        group_tasks_by_hierarchy,
        load_task_detail,
        load_task_cards,
    )
    from src.cyberagent.ui.teams_data import load_teams_with_members
    from src.cyberagent.ui.memory_data import load_memory_entries
    from src.cyberagent.ui.dashboard_log_badge import count_warnings_errors
    from src.cyberagent.core.paths import get_logs_dir
    from src.cli_session import list_inbox_entries, resolve_pending_question
except ModuleNotFoundError:
    from kanban_data import (
        KANBAN_STATUSES,
        group_tasks_by_hierarchy,
        load_task_detail,
        load_task_cards,
    )
    from teams_data import load_teams_with_members
    from memory_data import load_memory_entries
    from dashboard_log_badge import count_warnings_errors
    from src.cyberagent.core.paths import get_logs_dir
    from cli_session import list_inbox_entries, resolve_pending_question


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


def _open_task_details(st: Any, task_id: int) -> None:
    st.session_state["dashboard_selected_task_id"] = task_id
    st.session_state["dashboard_page"] = "Task Details"
    st.rerun()


def _select_page_with_buttons(st: Any, pages: list[str], current_page: str) -> str:
    selected_page = current_page if current_page in pages else pages[0]
    st.sidebar.markdown("### Pages")
    st.sidebar.caption(f"Current: {selected_page}")
    for page in pages:
        label = page if page != selected_page else f"{page} (Current)"
        if st.sidebar.button(
            label,
            key=f"dashboard_page_{page.lower().replace(' ', '_')}",
            use_container_width=True,
        ):
            selected_page = page
    return selected_page


def _render_case_judgement(st: Any, case_judgement: str | None) -> None:
    if not case_judgement:
        st.caption("No case judgement recorded.")
        return
    try:
        parsed = json.loads(case_judgement)
    except json.JSONDecodeError:
        st.code(case_judgement)
        return
    if not isinstance(parsed, list):
        st.code(case_judgement)
        return
    if len(parsed) == 0:
        st.caption("No case judgement recorded.")
        return
    st.dataframe(parsed, width="stretch", hide_index=True)


def _render_task_details_page(st: Any, title_col: Any) -> None:
    task_id = st.session_state.get("dashboard_selected_task_id")
    with title_col:
        st.title("CyberneticAgents Task Details")
    if task_id is None:
        st.info("Select a task from the Kanban board.")
        return
    task = load_task_detail(int(task_id))
    if task is None:
        st.error(f"Task #{task_id} not found.")
        return

    st.subheader(f"Task #{task.id}: {task.name}")
    st.markdown(
        "\n".join(
            [
                f"- Status: `{task.status}`",
                f"- Assignee: `{task.assignee or '-'}`",
                f"- Team: `{task.team_name}` (`{task.team_id}`)",
                f"- Purpose: `{task.purpose_name or '-'}`",
                f"- Strategy: `{task.strategy_name or '-'}`",
                f"- Initiative: `{task.initiative_name or '-'}` (`{task.initiative_id or '-'}`)",
            ]
        )
    )
    st.subheader("Task Content")
    st.write(task.content or "-")
    st.subheader("Status Reasoning")
    st.write(task.reasoning or "-")
    st.subheader("Task Result")
    st.write(task.result or "-")
    st.subheader("Case Judgement")
    _render_case_judgement(st, task.case_judgement)
    if st.button("Back to Kanban"):
        st.session_state["dashboard_page"] = "Kanban"
        st.rerun()


def render_inbox_page(st: Any) -> None:
    include_answered = st.checkbox("Include answered questions", value=False)
    entries = list_inbox_entries()
    if not include_answered:
        entries = [
            entry
            for entry in entries
            if not (entry.kind == "system_question" and entry.status == "answered")
        ]
    if not entries:
        st.info("No messages in inbox.")
        return
    if any(entry.channel == "telegram" for entry in entries) and not os.environ.get(
        "TELEGRAM_BOT_TOKEN"
    ):
        st.caption("Telegram delivery is disabled (missing TELEGRAM_BOT_TOKEN).")

    user_prompts = [entry for entry in entries if entry.kind == "user_prompt"]
    system_questions = [entry for entry in entries if entry.kind == "system_question"]
    system_responses = [entry for entry in entries if entry.kind == "system_response"]

    if user_prompts:
        st.subheader("User Prompts")
        st.dataframe(
            [
                {
                    "id": entry.entry_id,
                    "content": entry.content,
                    "channel": entry.channel,
                    "session_id": entry.session_id,
                }
                for entry in user_prompts
            ],
            width="stretch",
            hide_index=True,
        )
    if system_questions:
        st.subheader("System Questions")
        st.dataframe(
            [
                {
                    "id": entry.entry_id,
                    "content": entry.content,
                    "asked_by": entry.asked_by or "System4",
                    "status": entry.status or "pending",
                    "answer": entry.answer or "",
                    "channel": entry.channel,
                    "session_id": entry.session_id,
                }
                for entry in system_questions
            ],
            width="stretch",
            hide_index=True,
        )
        pending_questions = [
            entry
            for entry in system_questions
            if (entry.status or "pending") == "pending"
        ]
        if pending_questions:
            st.subheader("Answer Pending Questions")
            for entry in pending_questions:
                answer_key = f"inbox_answer_{entry.entry_id}"
                submit_key = f"inbox_answer_submit_{entry.entry_id}"
                answer = st.text_input(
                    f"Answer question #{entry.entry_id}: {entry.content}",
                    value="",
                    key=answer_key,
                )
                if not st.button(
                    f"Submit answer #{entry.entry_id}",
                    key=submit_key,
                ):
                    continue
                normalized = answer.strip()
                if not normalized:
                    st.error(f"Answer cannot be empty for question #{entry.entry_id}.")
                    continue
                resolved = resolve_pending_question(
                    normalized,
                    channel=entry.channel,
                    session_id=entry.session_id,
                )
                if resolved is None:
                    st.error(f"Question #{entry.entry_id} is no longer pending.")
                    continue
                st.success(f"Answer submitted for question #{entry.entry_id}.")
    if system_responses:
        st.subheader("System Responses")
        st.dataframe(
            [
                {
                    "id": entry.entry_id,
                    "content": entry.content,
                    "channel": entry.channel,
                    "session_id": entry.session_id,
                }
                for entry in system_responses
            ],
            width="stretch",
            hide_index=True,
        )


def render_memory_page(st: Any) -> None:
    scope = st.sidebar.selectbox(
        "Memory Scope",
        options=[None, "agent", "team", "global"],
        format_func=lambda value: "All scopes" if value is None else value,
    )
    namespace = st.sidebar.text_input("Memory Namespace", value="").strip() or None
    source = st.sidebar.selectbox(
        "Memory Source",
        options=[None, "import", "tool", "manual", "reflection"],
        format_func=lambda value: "All sources" if value is None else value,
    )
    tag_contains = st.sidebar.text_input("Tag Contains", value="").strip() or None
    page_size = int(
        st.sidebar.number_input(
            "Memory Page Size",
            min_value=10,
            max_value=200,
            value=50,
            step=10,
        )
    )
    page = int(
        st.sidebar.number_input(
            "Memory Page",
            min_value=1,
            max_value=1000,
            value=1,
            step=1,
        )
    )
    offset = (page - 1) * page_size
    try:
        entries, total = load_memory_entries(
            scope=scope,
            namespace=namespace,
            tag_contains=tag_contains,
            source=source,
            limit=page_size,
            offset=offset,
        )
    except Exception as exc:
        st.error(f"Failed to load memory entries: {exc}")
        return
    if not entries:
        st.info("No memory entries match current filters.")
        return
    st.caption(f"Showing {len(entries)} of {total} entries.")
    st.dataframe(
        [
            {
                "id": entry.id,
                "scope": entry.scope,
                "namespace": entry.namespace,
                "owner_agent_id": entry.owner_agent_id,
                "content_preview": entry.content_preview,
                "tags": ", ".join(entry.tags),
                "source": entry.source,
                "priority": entry.priority,
                "layer": entry.layer,
                "confidence": entry.confidence,
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
            }
            for entry in entries
        ],
        width="stretch",
        hide_index=True,
    )
    for entry in entries:
        with st.expander(f"Entry {entry.id}"):
            st.write(entry.content_full)
            st.write(
                {
                    "scope": entry.scope,
                    "namespace": entry.namespace,
                    "owner_agent_id": entry.owner_agent_id,
                    "tags": entry.tags,
                    "source": entry.source,
                    "priority": entry.priority,
                    "layer": entry.layer,
                    "confidence": entry.confidence,
                    "created_at": entry.created_at,
                    "updated_at": entry.updated_at,
                }
            )


def render_board() -> None:
    st = _load_streamlit()
    st.set_page_config(page_title="CyberneticAgents Kanban", layout="wide")

    warnings, errors = count_warnings_errors(get_logs_dir())
    title_col, badge_col = st.columns([8, 2])
    with badge_col:
        st.markdown(f"⚠️ **{warnings}**  ❌ **{errors}**")

    pages = ["Kanban", "Teams", "Inbox", "Memory"]
    if st.session_state.get("dashboard_selected_task_id") is not None:
        pages.append("Task Details")
    current_page = st.session_state.get("dashboard_page", "Kanban")
    page = _select_page_with_buttons(st, pages, current_page)
    st.session_state["dashboard_page"] = page
    if page == "Teams":
        with title_col:
            st.title("CyberneticAgents Teams (Read-Only)")
        render_teams_page(st)
        return
    if page == "Inbox":
        with title_col:
            st.title("CyberneticAgents Inbox (Read-Only)")
        render_inbox_page(st)
        return
    if page == "Memory":
        with title_col:
            st.title("CyberneticAgents Memory (Read-Only)")
        render_memory_page(st)
        return
    if page == "Task Details":
        _render_task_details_page(st, title_col)
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
                if column.button(
                    f"#{task.id} {task.name}",
                    key=f"task_open_{task.id}",
                    width="stretch",
                ):
                    _open_task_details(st, task.id)
                column.caption(f"Assignee: {assignee_text}")
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
        width="stretch",
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
            width="stretch",
            hide_index=True,
        )


def main() -> None:
    render_board()


if __name__ == "__main__":
    main()
