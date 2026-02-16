from __future__ import annotations

from typing import cast

from src.cli_session import AnsweredQuestion, InboxEntry
from src.cyberagent.ui import dashboard
from src.cyberagent.ui.memory_data import MemoryEntryView
from src.cyberagent.ui.teams_data import TeamMemberView, TeamWithMembersView


class _FakeStreamlit:
    def __init__(self) -> None:
        self.subheaders: list[str] = []
        self.captions: list[str] = []
        self.dataframe_calls: list[dict[str, object]] = []
        self.dataframe_data: list[object] = []
        self.info_messages: list[str] = []
        self.success_messages: list[str] = []
        self.error_messages: list[str] = []
        self.code_values: list[str] = []
        self.checkbox_values: dict[str, bool] = {}
        self.text_input_values: dict[str, str] = {}
        self.button_values: dict[str, bool] = {}
        self.write_values: list[object] = []

    def subheader(self, text: str) -> None:
        self.subheaders.append(text)

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def info(self, text: str) -> None:
        self.info_messages.append(text)

    def success(self, text: str) -> None:
        self.success_messages.append(text)

    def error(self, text: str) -> None:
        self.error_messages.append(text)

    def code(self, text: str) -> None:
        self.code_values.append(text)

    def write(self, value: object) -> None:
        self.write_values.append(value)

    def checkbox(self, label: str, value: bool = False) -> bool:
        return self.checkbox_values.get(label, value)

    def text_input(self, _label: str, value: str = "", key: str | None = None) -> str:
        if key is None:
            return value
        return self.text_input_values.get(key, value)

    def button(self, _label: str, key: str | None = None) -> bool:
        if key is None:
            return False
        return self.button_values.get(key, False)

    def dataframe(self, _data: object, **kwargs: object) -> None:
        self.dataframe_data.append(_data)
        self.dataframe_calls.append(kwargs)


def test_render_teams_page_uses_width_stretch(
    monkeypatch,
) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(
        dashboard,
        "load_teams_with_members",
        lambda: [
            TeamWithMembersView(
                team_id=1,
                team_name="team-1",
                policies=["p1"],
                permissions=["skill.a"],
                policy_details=["p1: policy content"],
                members=[
                    TeamMemberView(
                        id=10,
                        name="System1/team-1",
                        system_type="OPERATION",
                        agent_id_str="System1/team-1",
                        policies=["sp1"],
                        permissions=["skill.a"],
                        policy_details=["sp1: system policy content"],
                    )
                ],
            )
        ],
    )

    dashboard.render_teams_page(fake_st)

    assert len(fake_st.dataframe_calls) == 2
    kwargs = fake_st.dataframe_calls[0]
    assert kwargs.get("width") == "stretch"
    assert "use_container_width" not in kwargs
    policy_rows = cast(list[dict[str, object]], fake_st.dataframe_data[0])
    assert policy_rows == [{"policy": "p1", "description": "policy content"}]
    rows = cast(list[dict[str, object]], fake_st.dataframe_data[1])
    assert rows[0]["system_policies"] == "sp1"


def test_render_teams_page_no_teams_shows_info(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(dashboard, "load_teams_with_members", lambda: [])

    dashboard.render_teams_page(fake_st)

    assert fake_st.info_messages == ["No teams found."]


def test_render_case_judgement_uses_dataframe_width_stretch() -> None:
    fake_st = _FakeStreamlit()

    dashboard._render_case_judgement(fake_st, '[{"judge":"ok"}]')

    assert len(fake_st.dataframe_calls) == 1
    kwargs = fake_st.dataframe_calls[0]
    assert kwargs.get("width") == "stretch"
    assert "use_container_width" not in kwargs


def test_render_case_judgement_invalid_json_uses_code() -> None:
    fake_st = _FakeStreamlit()

    dashboard._render_case_judgement(fake_st, "not-json")

    assert fake_st.code_values == ["not-json"]


def test_render_case_judgement_includes_policy_content(monkeypatch) -> None:
    fake_st = _FakeStreamlit()

    policy = type(
        "Policy",
        (),
        {"name": "evidence_requirements", "content": "Include sources."},
    )()
    monkeypatch.setattr(
        dashboard.policy_service, "get_policy_by_id", lambda _policy_id: policy
    )

    dashboard._render_case_judgement(
        fake_st,
        '[{"policy_id":2,"judgement":"Violated","reasoning":"No source provided."}]',
    )

    assert len(fake_st.dataframe_data) == 1
    rows = fake_st.dataframe_data[0]
    assert isinstance(rows, list)
    assert rows[0]["policy_name"] == "evidence_requirements"
    assert rows[0]["policy_content"] == "Include sources."


def test_render_inbox_page_excludes_answered_questions_by_default(
    monkeypatch,
) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(
        dashboard,
        "list_inbox_entries",
        lambda **_: [
            InboxEntry(
                entry_id=1,
                kind="user_prompt",
                content="hello",
                created_at=1.0,
                channel="cli",
                session_id="cli-main",
            ),
            InboxEntry(
                entry_id=2,
                kind="system_question",
                content="pending question",
                created_at=2.0,
                channel="cli",
                session_id="cli-main",
                asked_by="System4/root",
                status="pending",
            ),
            InboxEntry(
                entry_id=3,
                kind="system_question",
                content="answered question",
                created_at=3.0,
                channel="cli",
                session_id="cli-main",
                asked_by="System4/root",
                status="answered",
                answer="done",
            ),
            InboxEntry(
                entry_id=4,
                kind="system_response",
                content="status update",
                created_at=4.0,
                channel="cli",
                session_id="cli-main",
            ),
        ],
    )

    dashboard.render_inbox_page(fake_st)

    assert fake_st.subheaders == [
        "User Prompts",
        "Answer Pending Questions",
        "System Questions",
        "System Responses",
    ]
    question_rows = fake_st.dataframe_data[1]
    assert isinstance(question_rows, list)
    assert [row["content"] for row in question_rows] == ["pending question"]


def test_render_inbox_page_can_include_answered_questions(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    fake_st.checkbox_values["Include answered questions"] = True
    monkeypatch.setattr(
        dashboard,
        "list_inbox_entries",
        lambda **_: [
            InboxEntry(
                entry_id=10,
                kind="system_question",
                content="pending question",
                created_at=10.0,
                channel="cli",
                session_id="cli-main",
                asked_by="System4/root",
                status="pending",
            ),
            InboxEntry(
                entry_id=11,
                kind="system_question",
                content="answered question",
                created_at=11.0,
                channel="cli",
                session_id="cli-main",
                asked_by="System4/root",
                status="answered",
                answer="done",
            ),
        ],
    )

    dashboard.render_inbox_page(fake_st)

    question_rows = fake_st.dataframe_data[0]
    assert isinstance(question_rows, list)
    assert [row["content"] for row in question_rows] == [
        "pending question",
        "answered question",
    ]


def test_render_inbox_page_can_answer_pending_question(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    fake_st.text_input_values["inbox_answer_21"] = "Shipped"
    fake_st.button_values["inbox_answer_submit_21"] = True
    monkeypatch.setattr(
        dashboard,
        "list_inbox_entries",
        lambda **_: [
            InboxEntry(
                entry_id=21,
                kind="system_question",
                content="What happened?",
                created_at=21.0,
                channel="cli",
                session_id="cli-main",
                asked_by="System4/root",
                status="pending",
            )
        ],
    )
    resolved_calls: list[tuple[str, str | None, str | None]] = []

    def _fake_resolve(
        answer: str, channel: str | None = None, session_id: str | None = None
    ) -> AnsweredQuestion:
        resolved_calls.append((answer, channel, session_id))
        return AnsweredQuestion(
            question_id=21,
            content="What happened?",
            asked_by="System4/root",
            created_at=21.0,
            answer=answer,
            answered_at=22.0,
            channel=channel or "cli",
            session_id=session_id or "cli-main",
        )

    monkeypatch.setattr(dashboard, "resolve_pending_question", _fake_resolve)

    dashboard.render_inbox_page(fake_st)

    assert resolved_calls == [("Shipped", "cli", "cli-main")]
    assert fake_st.success_messages == ["Answer submitted for question #21."]


def test_render_inbox_page_rejects_empty_answer(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    fake_st.text_input_values["inbox_answer_22"] = "   "
    fake_st.button_values["inbox_answer_submit_22"] = True
    monkeypatch.setattr(
        dashboard,
        "list_inbox_entries",
        lambda **_: [
            InboxEntry(
                entry_id=22,
                kind="system_question",
                content="Need answer",
                created_at=22.0,
                channel="cli",
                session_id="cli-main",
                status="pending",
            )
        ],
    )
    called = {"resolve": False}

    def _fake_resolve(*_args, **_kwargs):
        called["resolve"] = True
        return None

    monkeypatch.setattr(dashboard, "resolve_pending_question", _fake_resolve)

    dashboard.render_inbox_page(fake_st)

    assert called["resolve"] is False
    assert fake_st.error_messages == ["Answer cannot be empty for question #22."]


def test_render_inbox_page_answers_only_first_pending_question(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    fake_st.text_input_values["inbox_answer_30"] = "First"
    fake_st.text_input_values["inbox_answer_31"] = "Second"
    fake_st.button_values["inbox_answer_submit_30"] = True
    fake_st.button_values["inbox_answer_submit_31"] = True
    monkeypatch.setattr(
        dashboard,
        "list_inbox_entries",
        lambda **_: [
            InboxEntry(
                entry_id=30,
                kind="system_question",
                content="First question",
                created_at=30.0,
                channel="cli",
                session_id="cli-main",
                status="pending",
            ),
            InboxEntry(
                entry_id=31,
                kind="system_question",
                content="Second question",
                created_at=31.0,
                channel="cli",
                session_id="cli-main",
                status="pending",
            ),
        ],
    )
    resolved_calls: list[tuple[str, str | None, str | None]] = []

    def _fake_resolve(
        answer: str, channel: str | None = None, session_id: str | None = None
    ) -> AnsweredQuestion:
        resolved_calls.append((answer, channel, session_id))
        return AnsweredQuestion(
            question_id=30,
            content="First question",
            asked_by="System4/root",
            created_at=30.0,
            answer=answer,
            answered_at=31.0,
            channel=channel or "cli",
            session_id=session_id or "cli-main",
        )

    monkeypatch.setattr(dashboard, "resolve_pending_question", _fake_resolve)

    dashboard.render_inbox_page(fake_st)

    assert resolved_calls == [("First", "cli", "cli-main")]
    assert fake_st.success_messages == ["Answer submitted for question #30."]



def test_render_execution_log_fallbacks_to_code_for_invalid_json() -> None:
    fake_st = _FakeStreamlit()

    dashboard._render_execution_log(fake_st, "not-json")

    assert fake_st.code_values == ["not-json"]


def test_render_memory_page_shows_entries(monkeypatch) -> None:
    class _FakeSidebar:
        def selectbox(self, _label: str, options: list[object], format_func=None):
            _ = format_func
            return options[0]

        def text_input(self, _label: str, value: str = "") -> str:
            return value

        def number_input(
            self,
            _label: str,
            min_value: int = 0,
            max_value: int = 1000,
            value: int = 0,
            step: int = 1,
        ) -> int:
            _ = (min_value, max_value, step)
            return value

    class _MemoryStreamlit(_FakeStreamlit):
        def __init__(self) -> None:
            super().__init__()
            self.sidebar = _FakeSidebar()
            self.expander_calls: list[str] = []

        class _ExpanderCtx:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        def expander(self, label: str):
            self.expander_calls.append(label)
            return self._ExpanderCtx()

    monkeypatch.setattr(
        dashboard,
        "load_memory_entries",
        lambda **_kwargs: (
            [
                MemoryEntryView(
                    id="mem-1",
                    scope="global",
                    namespace="user",
                    owner_agent_id="System4/root",
                    content_preview="PKM file: notes/alpha.md",
                    content_full="PKM file: notes/alpha.md\n\nAlpha",
                    tags=["onboarding", "pkm", "pkm_file"],
                    source="import",
                    priority="high",
                    layer="long_term",
                    confidence=0.8,
                    created_at="2026-02-09T12:00:00+00:00",
                    updated_at="2026-02-09T12:00:00+00:00",
                )
            ],
            1,
        ),
    )
    st = _MemoryStreamlit()
    dashboard.render_memory_page(st)

    assert len(st.dataframe_data) == 1
    rows = st.dataframe_data[0]
    assert isinstance(rows, list)
    assert rows[0]["id"] == "mem-1"
    assert st.expander_calls == ["Entry mem-1"]


def test_select_page_with_buttons_returns_current_when_no_clicks() -> None:
    class _Sidebar:
        def __init__(self) -> None:
            self.markdowns: list[str] = []
            self.captions: list[str] = []

        def markdown(self, text: str) -> None:
            self.markdowns.append(text)

        def caption(self, text: str) -> None:
            self.captions.append(text)

        def button(
            self, _label: str, key: str | None = None, use_container_width: bool = False
        ) -> bool:
            _ = (key, use_container_width)
            return False

    class _St:
        def __init__(self) -> None:
            self.sidebar = _Sidebar()

    st = _St()
    selected = dashboard._select_page_with_buttons(
        st,
        pages=["Kanban", "Teams", "Inbox"],
        current_page="Teams",
    )

    assert selected == "Teams"
    assert st.sidebar.markdowns == ["### Pages"]
    assert st.sidebar.captions == ["Current: Teams"]


def test_select_page_with_buttons_updates_when_clicked() -> None:
    class _Sidebar:
        def markdown(self, _text: str) -> None:
            return None

        def caption(self, _text: str) -> None:
            return None

        def button(
            self, _label: str, key: str | None = None, use_container_width: bool = False
        ) -> bool:
            _ = use_container_width
            return key == "dashboard_page_inbox"

    class _St:
        def __init__(self) -> None:
            self.sidebar = _Sidebar()

    st = _St()
    selected = dashboard._select_page_with_buttons(
        st,
        pages=["Kanban", "Teams", "Inbox"],
        current_page="Kanban",
    )

    assert selected == "Inbox"



def test_render_board_excludes_kanban_page(monkeypatch) -> None:
    captured_pages: dict[str, list[str]] = {}

    class _Sidebar:
        def markdown(self, _text: str) -> None:
            return None

        def caption(self, _text: str) -> None:
            return None

        def button(
            self,
            _label: str,
            key: str | None = None,
            use_container_width: bool = False,
        ) -> bool:
            _ = (key, use_container_width)
            return False

        def selectbox(self, _label: str, options: list[object], format_func=None):
            _ = format_func
            return options[0]

        def text_input(self, _label: str, value: str = "") -> str:
            return value

        def number_input(
            self,
            _label: str,
            min_value: int = 0,
            max_value: int = 1000,
            value: int = 0,
            step: int = 1,
        ) -> int:
            _ = (min_value, max_value, step)
            return value

    class _Column:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class _FakeStreamlit:
        def __init__(self) -> None:
            self.sidebar = _Sidebar()
            self.session_state: dict[str, object] = {}

        def set_page_config(self, **_kwargs: object) -> None:
            return None

        def columns(self, _spec: list[int]):
            return (_Column(), _Column())

        def markdown(self, _text: str) -> None:
            return None

        def title(self, _text: str) -> None:
            return None

    fake_st = _FakeStreamlit()

    def _capture_pages(_st: object, pages: list[str], current_page: str) -> str:
        _ = current_page
        captured_pages["pages"] = pages
        return "Teams"

    monkeypatch.setattr(dashboard, "_load_streamlit", lambda: fake_st)
    monkeypatch.setattr(dashboard, "count_warnings_errors", lambda _path: (0, 0))
    monkeypatch.setattr(dashboard, "_select_page_with_buttons", _capture_pages)
    monkeypatch.setattr(dashboard, "render_teams_page", lambda _st: None)

    dashboard.render_board()

    assert "Kanban" not in captured_pages["pages"]
