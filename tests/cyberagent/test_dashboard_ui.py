from __future__ import annotations

from src.cyberagent.ui import dashboard
from src.cyberagent.ui.teams_data import TeamMemberView, TeamWithMembersView


class _FakeStreamlit:
    def __init__(self) -> None:
        self.dataframe_calls: list[dict[str, object]] = []
        self.info_messages: list[str] = []
        self.code_values: list[str] = []

    def subheader(self, _text: str) -> None:
        return

    def caption(self, _text: str) -> None:
        return

    def info(self, text: str) -> None:
        self.info_messages.append(text)

    def code(self, text: str) -> None:
        self.code_values.append(text)

    def dataframe(self, _data: object, **kwargs: object) -> None:
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
