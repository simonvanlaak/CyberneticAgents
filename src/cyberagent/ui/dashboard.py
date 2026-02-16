from __future__ import annotations

import importlib
import json
import os
from typing import Any

try:
    from src.cyberagent.core.paths import get_logs_dir
    from src.cyberagent.services import policies as policy_service
    from src.cyberagent.ui.dashboard_log_badge import count_warnings_errors
    from src.cyberagent.ui.memory_data import load_memory_entries
    from src.cyberagent.ui.teams_data import load_teams_with_members
    from src.cli_session import list_inbox_entries, resolve_pending_question
except ModuleNotFoundError:
    from src.cyberagent.core.paths import get_logs_dir
    from src.cyberagent.services import policies as policy_service
    from cli_session import list_inbox_entries, resolve_pending_question
    from dashboard_log_badge import count_warnings_errors
    from memory_data import load_memory_entries
    from teams_data import load_teams_with_members


def _load_streamlit() -> Any:
    try:
        return importlib.import_module("streamlit")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Streamlit is not installed. Add 'streamlit' to dependencies and install."
        ) from exc


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
    st.dataframe(
        _enrich_case_judgement_with_policy_content(parsed),
        width="stretch",
        hide_index=True,
    )


def _render_execution_log(st: Any, execution_log: str | None) -> None:
    if not execution_log:
        st.caption("No execution log recorded.")
        return
    try:
        parsed = json.loads(execution_log)
    except json.JSONDecodeError:
        if hasattr(st, "code"):
            st.code(execution_log)
        else:
            st.write(execution_log)
        return
    if not isinstance(parsed, list) or len(parsed) == 0:
        if hasattr(st, "code"):
            st.code(execution_log)
        else:
            st.write(execution_log)
        return

    rows = _build_execution_log_rows(parsed)
    if hasattr(st, "dataframe"):
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.write(rows)


def _build_execution_log_rows(entries: list[object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, entry in enumerate(entries, 1):
        if isinstance(entry, dict):
            step_type = str(entry.get("type", "-"))
            tool_name = (
                _extract_tool_name(entry) if _is_tool_call_event(step_type) else "-"
            )
            source = str(entry.get("source", "-"))
            summary = _summarize_execution_entry(entry)
        else:
            step_type = type(entry).__name__
            tool_name = "-"
            source = "-"
            summary = _truncate_text(str(entry), 200)
        rows.append(
            {
                "step": index,
                "type": step_type,
                "tool": tool_name,
                "source": source,
                "summary": summary,
            }
        )
    return rows


def _is_tool_call_event(step_type: str) -> bool:
    normalized = step_type.strip().lower()
    return "toolcall" in normalized or ("tool" in normalized and "call" in normalized)


def _extract_tool_name(entry: dict[str, object]) -> str:
    name = entry.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()

    content = entry.get("content")
    if isinstance(content, dict):
        content_name = content.get("name")
        if isinstance(content_name, str) and content_name.strip():
            return content_name.strip()
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                item_name = item.get("name")
                if isinstance(item_name, str) and item_name.strip():
                    return item_name.strip()

    return "-"


def _summarize_execution_entry(entry: dict[str, object]) -> str:
    chunks: list[str] = []
    name = entry.get("name")
    if isinstance(name, str) and name.strip():
        chunks.append(name.strip())
    model_text = entry.get("model_text")
    if isinstance(model_text, str) and model_text.strip():
        chunks.append(_truncate_text(model_text.strip(), 200))
    content = entry.get("content")
    content_summary = _summarize_execution_content(content)
    if content_summary is not None:
        chunks.append(content_summary)
    if not chunks:
        return "-"
    deduped: list[str] = []
    for chunk in chunks:
        if chunk not in deduped:
            deduped.append(chunk)
    return " | ".join(deduped[:2])


def _summarize_execution_content(content: object) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return _truncate_text(content.strip(), 200)
    if isinstance(content, list):
        if len(content) == 0:
            return "[]"
        first = _summarize_execution_content(content[0]) or str(content[0])
        if len(content) == 1:
            return first
        return f"{first} (+{len(content) - 1} more)"
    if isinstance(content, dict):
        name = content.get("name")
        payload = content.get("content")
        if isinstance(name, str) and isinstance(payload, str):
            return f"{name}: {_truncate_text(payload.strip(), 160)}"
        if isinstance(payload, str):
            return _truncate_text(payload.strip(), 200)
        return _truncate_text(json.dumps(content, ensure_ascii=True, default=str), 200)
    return _truncate_text(str(content), 200)


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _enrich_case_judgement_with_policy_content(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    enriched_rows: list[dict[str, object]] = []
    policy_cache: dict[int, tuple[str, str]] = {}
    for row in rows:
        enriched = dict(row)
        policy_id = row.get("policy_id")
        if not isinstance(policy_id, int):
            enriched_rows.append(enriched)
            continue
        if policy_id not in policy_cache:
            policy = policy_service.get_policy_by_id(policy_id)
            if policy is None:
                policy_cache[policy_id] = ("-", "-")
            else:
                policy_cache[policy_id] = (
                    str(getattr(policy, "name", "-")),
                    str(getattr(policy, "content", "-")),
                )
        policy_name, policy_content = policy_cache[policy_id]
        enriched["policy_name"] = policy_name
        enriched["policy_content"] = policy_content
        enriched_rows.append(enriched)
    return enriched_rows


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
        pending_questions = [
            entry
            for entry in system_questions
            if (entry.status or "pending") == "pending"
        ]
        if pending_questions:
            st.subheader("Answer Pending Questions")
            entry = pending_questions[0]
            answer_key = f"inbox_answer_{entry.entry_id}"
            submit_key = f"inbox_answer_submit_{entry.entry_id}"
            answer = st.text_input(
                f"Answer question #{entry.entry_id}: {entry.content}",
                value="",
                key=answer_key,
            )
            if st.button(
                f"Submit answer #{entry.entry_id}",
                key=submit_key,
            ):
                normalized = answer.strip()
                if not normalized:
                    st.error(f"Answer cannot be empty for question #{entry.entry_id}.")
                else:
                    resolved = resolve_pending_question(
                        normalized,
                        channel=entry.channel,
                        session_id=entry.session_id,
                    )
                    if resolved is None:
                        st.error(f"Question #{entry.entry_id} is no longer pending.")
                    else:
                        st.success(f"Answer submitted for question #{entry.entry_id}.")
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
    st.set_page_config(page_title="CyberneticAgents Operations Dashboard", layout="wide")

    warnings, errors = count_warnings_errors(get_logs_dir())
    title_col, badge_col = st.columns([8, 2])
    with badge_col:
        st.markdown(f"⚠️ **{warnings}**  ❌ **{errors}**")

    pages = ["Teams", "Inbox", "Memory"]
    current_page = st.session_state.get("dashboard_page", "Teams")
    page = _select_page_with_buttons(st, pages, str(current_page))
    st.session_state["dashboard_page"] = page

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

    with title_col:
        st.title("CyberneticAgents Teams (Read-Only)")
    render_teams_page(st)


def render_teams_page(st: Any) -> None:
    teams = load_teams_with_members()
    if not teams:
        st.info("No teams found.")
        return

    for team in teams:
        st.subheader(f"Team {team.team_name} ({team.team_id})")
        team_policy_values = getattr(team, "policy_details", None) or team.policies
        team_permissions_text = ", ".join(team.permissions) if team.permissions else "-"
        st.caption("Team policies")
        st.dataframe(
            _build_policy_table_rows(team_policy_values),
            width="stretch",
            hide_index=True,
        )
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


def _build_policy_table_rows(policy_values: list[str]) -> list[dict[str, str]]:
    if not policy_values:
        return [{"policy": "-", "description": "-"}]
    rows: list[dict[str, str]] = []
    for value in policy_values:
        policy_text = str(value).strip()
        if ": " not in policy_text:
            rows.append({"policy": policy_text or "-", "description": "-"})
            continue
        policy_name, policy_description = policy_text.split(": ", 1)
        rows.append(
            {
                "policy": policy_name.strip() or "-",
                "description": policy_description.strip() or "-",
            }
        )
    return rows


def main() -> None:
    render_board()


if __name__ == "__main__":
    main()
