from __future__ import annotations

from src.cli_session import AnsweredQuestion, InboxEntry
from src.cyberagent.ui import dashboard
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
                members=[
                    TeamMemberView(
                        id=10,
                        name="System1/team-1",
                        system_type="OPERATION",
                        agent_id_str="System1/team-1",
                        policies=["sp1"],
                        permissions=["skill.a"],
                    )
                ],
            )
        ],
    )

    dashboard.render_teams_page(fake_st)

    assert len(fake_st.dataframe_calls) == 1
    kwargs = fake_st.dataframe_calls[0]
    assert kwargs.get("width") == "stretch"
    assert "use_container_width" not in kwargs


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
        "System Questions",
        "Answer Pending Questions",
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
