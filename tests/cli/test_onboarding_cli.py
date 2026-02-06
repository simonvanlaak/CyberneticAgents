from __future__ import annotations

import argparse
import os
from pathlib import Path
import pytest

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.cli import onboarding_docker
from src.cyberagent.cli import onboarding_optional
from src.cyberagent.cli import onboarding_telegram
from src.cyberagent.cli import onboarding_vault
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.procedure import Procedure
from src.cyberagent.db.models.procedure_run import ProcedureRun
from src.cyberagent.db.models.procedure_task import ProcedureTask
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.db.models.initiative import Initiative
from src.cyberagent.db.models.purpose import Purpose
from src.cyberagent.db.models.strategy import Strategy
from src.cyberagent.cli import agent_message_queue
from src.cyberagent.services import systems as systems_service, teams as teams_service
from src.cyberagent.tools.cli_executor.skill_loader import SkillDefinition
from src.cyberagent.cli import onboarding_memory
from src.cyberagent.memory.models import MemoryScope
from src.enums import ProcedureStatus
from src.enums import SystemType


def _clear_teams() -> None:
    session = next(get_db())
    try:
        session.query(ProcedureTask).delete()
        session.query(ProcedureRun).delete()
        session.query(Procedure).delete()
        session.query(System).delete()
        session.query(Team).delete()
        session.commit()
    finally:
        session.close()


def _default_onboarding_args() -> argparse.Namespace:
    return argparse.Namespace(
        user_name="Test User",
        pkm_source="github",
        repo_url="https://github.com/example/repo",
        profile_links=["https://example.com/profile"],
        token_env="GITHUB_READONLY_TOKEN",
        token_username="x-access-token",
    )


def test_handle_onboarding_creates_default_team(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")
    monkeypatch.setattr(
        onboarding_cli, "_run_discovery_onboarding", lambda *_: summary_path
    )
    monkeypatch.setattr(
        onboarding_cli, "_trigger_onboarding_initiative", lambda *_, **__: True
    )
    start_calls: list[int] = []

    def _fake_start(team_id: int) -> int | None:
        start_calls.append(team_id)
        return 1234

    monkeypatch.setattr(onboarding_cli, "_start_runtime_after_onboarding", _fake_start)

    exit_code = onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )
    captured = capsys.readouterr().out
    monkeypatch.undo()

    assert exit_code == 0
    assert "Created default team" in captured
    assert "cyberagent inbox" in captured
    assert len(start_calls) == 1

    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == "root").first()
        assert team is not None
        assert start_calls[0] == team.id
    finally:
        session.close()


def test_ensure_repo_root_env_var_writes_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(onboarding_cli, "get_repo_root", lambda: tmp_path)
    monkeypatch.delenv("CYBERAGENT_ROOT", raising=False)

    onboarding_cli._ensure_repo_root_env_var()

    env_path = tmp_path / ".env"
    assert env_path.exists()
    assert f"CYBERAGENT_ROOT={tmp_path.resolve()}" in env_path.read_text(
        encoding="utf-8"
    )
    assert os.environ.get("CYBERAGENT_ROOT") == str(tmp_path.resolve())


def test_ensure_repo_root_env_var_preserves_existing_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(onboarding_cli, "get_repo_root", lambda: tmp_path)
    monkeypatch.delenv("CYBERAGENT_ROOT", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("CYBERAGENT_ROOT=/custom/root\n", encoding="utf-8")

    onboarding_cli._ensure_repo_root_env_var()

    assert env_path.read_text(encoding="utf-8") == "CYBERAGENT_ROOT=/custom/root\n"
    assert os.environ.get("CYBERAGENT_ROOT") == "/custom/root"


def test_handle_onboarding_skips_when_team_exists(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()
    session = next(get_db())
    try:
        session.add(Team(name="existing_team"))
        session.commit()
    finally:
        session.close()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")
    monkeypatch.setattr(
        onboarding_cli, "_run_discovery_onboarding", lambda *_: summary_path
    )
    monkeypatch.setattr(
        onboarding_cli, "_trigger_onboarding_initiative", lambda *_, **__: True
    )
    start_calls: list[int] = []

    def _fake_start(team_id: int) -> int | None:
        start_calls.append(team_id)
        return 1234

    monkeypatch.setattr(onboarding_cli, "_start_runtime_after_onboarding", _fake_start)
    exit_code = onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )
    captured = capsys.readouterr().out
    monkeypatch.undo()

    assert exit_code == 0
    assert "Team already exists" in captured
    assert "cyberagent inbox" in captured
    assert len(start_calls) == 1

    session = next(get_db())
    try:
        team = session.query(Team).first()
        assert team is not None
        assert session.query(Team).count() == 1
        assert start_calls[0] == team.id
    finally:
        session.close()


def test_handle_onboarding_requires_technical_checks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()

    monkeypatch.setattr(
        onboarding_cli, "run_technical_onboarding_checks", lambda: False
    )
    start_calls: list[int] = []

    def _fake_start(team_id: int) -> int | None:
        start_calls.append(team_id)
        return 1234

    monkeypatch.setattr(onboarding_cli, "_start_runtime_after_onboarding", _fake_start)

    exit_code = onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )
    captured = capsys.readouterr().out

    assert exit_code == 1
    assert "technical onboarding" in captured.lower()
    assert start_calls == []


def test_handle_onboarding_stops_when_discovery_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    monkeypatch.setattr(
        onboarding_cli, "_start_discovery_background", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        onboarding_cli, "start_onboarding_interview", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        onboarding_cli, "_trigger_onboarding_initiative", lambda *_, **__: True
    )
    start_calls: list[int] = []

    def _fake_start(team_id: int) -> int | None:
        start_calls.append(team_id)
        return 1234

    monkeypatch.setattr(onboarding_cli, "_start_runtime_after_onboarding", _fake_start)

    exit_code = onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "Starting PKM sync and profile discovery" in captured
    assert start_calls == [1]


def test_handle_onboarding_stops_when_trigger_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_teams()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    monkeypatch.setattr(
        onboarding_cli, "_start_discovery_background", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        onboarding_cli, "start_onboarding_interview", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        onboarding_cli, "_trigger_onboarding_initiative", lambda *_, **__: False
    )
    start_calls: list[int] = []

    def _fake_start(team_id: int) -> int | None:
        start_calls.append(team_id)
        return 1234

    monkeypatch.setattr(onboarding_cli, "_start_runtime_after_onboarding", _fake_start)

    exit_code = onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )

    assert exit_code == 1
    assert start_calls == []


def test_validate_onboarding_inputs_prompts_for_missing() -> None:
    args = argparse.Namespace(
        user_name=None,
        pkm_source=None,
        repo_url=None,
        profile_links=[],
        token_env="GITHUB_READONLY_TOKEN",
        token_username="x-access-token",
    )
    inputs = iter(
        [
            "Ada Lovelace",
            "2",
            "https://github.com/example/repo",
            "https://example.com/profile",
        ]
    )

    def _fake_input(_: str) -> str:
        return next(inputs)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(onboarding_cli.sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr("builtins.input", _fake_input)
    try:
        assert onboarding_cli._validate_onboarding_inputs(args) is True
    finally:
        monkeypatch.undo()

    assert args.user_name == "Ada Lovelace"
    assert args.pkm_source == "github"
    assert args.repo_url == "https://github.com/example/repo"
    assert args.profile_links == ["https://example.com/profile"]


def test_store_onboarding_memory_writes_global_entry(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("User onboarding summary.", encoding="utf-8")
    from src.cyberagent.tools.memory_crud import MemoryCrudArgs, MemoryCrudResponse

    recorded: dict[str, object] = {}

    class _FakeTool:
        async def run(  # type: ignore[no-untyped-def]
            self, args: MemoryCrudArgs, _token
        ) -> MemoryCrudResponse:
            recorded["args"] = args
            return MemoryCrudResponse(
                items=[], next_cursor=None, has_more=False, errors=[]
            )

    fake_system = System(
        id=10,
        team_id=1,
        name="System4/root",
        type=SystemType.INTELLIGENCE,
        agent_id_str="System4/root",
    )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_memory, "get_system_by_type", lambda *_: fake_system)
    monkeypatch.setattr(onboarding_memory, "_build_memory_tool", lambda *_: _FakeTool())
    try:
        onboarding_memory.store_onboarding_memory(1, summary_path)
    finally:
        monkeypatch.undo()

    args = recorded["args"]
    assert isinstance(args, MemoryCrudArgs)
    assert args.scope == MemoryScope.GLOBAL.value
    assert args.namespace == "user"


def test_handle_onboarding_seeds_default_sops(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")
    monkeypatch.setattr(
        onboarding_cli, "_run_discovery_onboarding", lambda *_: summary_path
    )
    monkeypatch.setattr(
        onboarding_cli, "_trigger_onboarding_initiative", lambda *_, **__: True
    )

    exit_code = onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )
    captured = capsys.readouterr().out
    monkeypatch.undo()

    assert exit_code == 0
    assert "cyberagent inbox" in captured

    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == "root").first()
        assert team is not None
        procedures = session.query(Procedure).filter(Procedure.team_id == team.id).all()
        procedure_names = {procedure.name for procedure in procedures}
        assert procedure_names == {"First Run Discovery"}
        assert all(
            procedure.status == ProcedureStatus.APPROVED for procedure in procedures
        )
        for procedure in procedures:
            tasks = (
                session.query(ProcedureTask)
                .filter(ProcedureTask.procedure_id == procedure.id)
                .order_by(ProcedureTask.position.asc())
                .all()
            )
            assert tasks
    finally:
        session.close()


def test_handle_onboarding_sets_root_team_envelope(tmp_path: Path) -> None:
    _clear_teams()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")
    monkeypatch.setattr(
        onboarding_cli, "_run_discovery_onboarding", lambda *_: summary_path
    )
    monkeypatch.setattr(
        onboarding_cli, "_trigger_onboarding_initiative", lambda *_, **__: True
    )

    onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )
    monkeypatch.undo()

    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == "root").first()
        assert team is not None
        allowed = teams_service.list_allowed_skills(team.id)
        assert "speech-to-text" in allowed
        system4 = systems_service.get_system_by_type(team.id, SystemType.INTELLIGENCE)
        assert "speech-to-text" not in systems_service.list_granted_skills(system4.id)
    finally:
        session.close()


def test_handle_onboarding_seeds_default_sops_once(tmp_path: Path) -> None:
    _clear_teams()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")
    monkeypatch.setattr(
        onboarding_cli, "_run_discovery_onboarding", lambda *_: summary_path
    )
    monkeypatch.setattr(
        onboarding_cli, "_trigger_onboarding_initiative", lambda *_, **__: True
    )

    onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )
    onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )
    monkeypatch.undo()

    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == "root").first()
        assert team is not None
        count = session.query(Procedure).filter(Procedure.team_id == team.id).count()
        assert count == 1
    finally:
        session.close()


def test_handle_onboarding_triggers_onboarding_sop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_teams()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)
    monkeypatch.setattr(
        onboarding_cli, "_start_runtime_after_onboarding", lambda *_: None
    )
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("summary", encoding="utf-8")
    monkeypatch.setattr(
        onboarding_cli, "_run_discovery_onboarding", lambda *_: summary_path
    )
    monkeypatch.setattr(
        agent_message_queue, "AGENT_MESSAGE_QUEUE_DIR", tmp_path / "agent_queue"
    )

    onboarding_cli.handle_onboarding(
        _default_onboarding_args(),
        'cyberagent suggest "Describe the task"',
        "cyberagent inbox",
    )

    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == "root").first()
        assert team is not None
        purpose = (
            session.query(Purpose)
            .filter(Purpose.team_id == team.id, Purpose.name == "Onboarding SOP")
            .first()
        )
        assert purpose is not None
        strategy = (
            session.query(Strategy)
            .filter(Strategy.team_id == team.id, Strategy.name == "Onboarding SOP")
            .first()
        )
        assert strategy is not None
        procedure = (
            session.query(Procedure)
            .filter(
                Procedure.team_id == team.id, Procedure.name == "First Run Discovery"
            )
            .first()
        )
        assert procedure is not None
        assert purpose.content == procedure.description
        run = session.query(ProcedureRun).first()
        assert run is not None
        initiative = (
            session.query(Initiative).filter(Initiative.id == run.initiative_id).first()
        )
        assert initiative is not None
    finally:
        session.close()

    queued = agent_message_queue.read_queued_agent_messages()
    assert len(queued) == 1
    assert queued[0].recipient == "System3/root"


def test_build_onboarding_prompt_includes_summary_path() -> None:
    prompt = onboarding_cli._build_onboarding_prompt(
        summary_path=Path("data/onboarding/20260204_120000/summary.md"),
        summary_text="Summary content here.",
    )
    assert "Onboarding Summary" in prompt
    assert "data/onboarding/20260204_120000/summary.md" in prompt


def test_technical_onboarding_requires_groq_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setattr(onboarding_cli, "_is_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "_check_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "check_docker_socket_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "check_docker_available", lambda: True)
    monkeypatch.setattr(onboarding_cli, "check_cli_tools_image_available", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_skill_root_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_network_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_required_tool_secrets", lambda: True)
    monkeypatch.setattr(onboarding_vault, "has_onepassword_auth", lambda: True)
    monkeypatch.setattr(
        onboarding_cli, "_load_technical_onboarding_state", lambda: None
    )
    monkeypatch.setattr(
        onboarding_cli, "_save_technical_onboarding_state", lambda *_: None
    )
    monkeypatch.setattr(onboarding_vault, "prompt_yes_no", lambda *_: False)

    assert onboarding_cli.run_technical_onboarding_checks() is False
    captured = capsys.readouterr().out
    assert "Activating features..." in captured
    assert "GROQ_API_KEY" in captured


def test_technical_onboarding_requires_onepassword_auth(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setattr(onboarding_cli, "_is_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "_check_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "check_docker_socket_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "check_docker_available", lambda: True)
    monkeypatch.setattr(onboarding_cli, "check_cli_tools_image_available", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_skill_root_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_network_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_required_tool_secrets", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: False)
    monkeypatch.setattr(
        onboarding_cli, "_load_technical_onboarding_state", lambda: None
    )
    monkeypatch.setattr(
        onboarding_cli, "_save_technical_onboarding_state", lambda *_: None
    )

    assert onboarding_cli.run_technical_onboarding_checks() is False
    captured = capsys.readouterr().out
    assert "1Password authentication" in captured


def test_onepassword_hint_when_op_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: False)
    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: None)

    assert onboarding_cli._check_onepassword_auth() is False
    captured = capsys.readouterr().out
    assert "OP_SERVICE_ACCOUNT_TOKEN" in captured


def test_has_onepassword_auth_accepts_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.setenv("OP_SESSION_CYBERAGENT", "session-token")

    assert onboarding_cli._has_onepassword_auth() is True


def test_has_onepassword_auth_loads_service_token_from_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.delenv("OP_SESSION_CYBERAGENT", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "OP_SERVICE_ACCOUNT_TOKEN=service-token\n", encoding="utf-8"
    )

    assert onboarding_cli._has_onepassword_auth() is True
    assert os.environ.get("OP_SERVICE_ACCOUNT_TOKEN") == "service-token"


def test_has_onepassword_auth_loads_service_token_from_parent_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.delenv("OP_SESSION_CYBERAGENT", raising=False)
    root = tmp_path / "repo"
    nested = root / "subdir"
    nested.mkdir(parents=True)
    (root / ".env").write_text(
        "OP_SERVICE_ACCOUNT_TOKEN=service-token\n", encoding="utf-8"
    )
    monkeypatch.chdir(nested)

    assert onboarding_cli._has_onepassword_auth() is True
    assert os.environ.get("OP_SERVICE_ACCOUNT_TOKEN") == "service-token"


def test_missing_brave_key_explains_vault_and_item(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)
    monkeypatch.setattr(onboarding_vault.shutil, "which", lambda *_: "/usr/bin/op")

    def _load_secret(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(onboarding_cli, "_load_secret_from_1password", _load_secret)
    monkeypatch.setattr(onboarding_vault, "prompt_yes_no", lambda *_: False)

    assert onboarding_cli._check_required_tool_secrets() is False
    captured = capsys.readouterr().out
    assert "CyberneticAgents" in captured
    assert "BRAVE_API_KEY" in captured


def test_prompt_store_secret_creates_vault_and_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    class DummyResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd: list[str], **kwargs) -> DummyResult:  # noqa: ANN001
        calls.append(cmd)
        if cmd[:3] == ["op", "item", "create"] and "--format" in cmd:
            return DummyResult(returncode=0, stdout='{"id":"check"}')
        if cmd[:3] == ["op", "item", "delete"]:
            return DummyResult(returncode=0)
        if cmd[:3] == ["op", "vault", "get"]:
            return DummyResult(returncode=1)
        if cmd[:3] == ["op", "vault", "create"]:
            return DummyResult(returncode=0)
        if cmd[:3] == ["op", "item", "create"]:
            return DummyResult(returncode=0)
        return DummyResult(returncode=0)

    monkeypatch.setattr(onboarding_vault.shutil, "which", lambda *_: "/usr/bin/op")
    monkeypatch.setattr(onboarding_vault, "has_onepassword_auth", lambda: True)
    monkeypatch.setattr(onboarding_vault, "prompt_yes_no", lambda *_: True)
    monkeypatch.setattr(onboarding_vault.getpass, "getpass", lambda *_: "secret")
    monkeypatch.setattr(onboarding_vault.subprocess, "run", fake_run)

    assert (
        onboarding_cli.prompt_store_secret_in_1password(
            env_name="BRAVE_API_KEY",
            description="Brave Search API key",
            doc_hint=None,
            vault_name="CyberneticAgents",
        )
        is True
    )
    assert ["op", "vault", "get", "CyberneticAgents"] in calls
    assert ["op", "vault", "create", "CyberneticAgents"] in calls
    assert any(cmd[:3] == ["op", "item", "create"] for cmd in calls)
    assert any("--title" in cmd and "BRAVE_API_KEY" in cmd for cmd in calls)


def test_optional_telegram_setup_prompts_when_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_USERNAME", raising=False)
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(onboarding_telegram.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(
        onboarding_telegram, "_load_secret_from_1password", lambda *_: None
    )
    monkeypatch.setattr(onboarding_telegram, "render_telegram_qr", lambda *_: "QR")
    monkeypatch.setattr(onboarding_vault.shutil, "which", lambda *_: "/usr/bin/op")
    monkeypatch.setattr(onboarding_vault, "has_onepassword_auth", lambda: True)
    monkeypatch.setattr(
        onboarding_vault, "check_onepassword_write_access", lambda *_: True
    )
    monkeypatch.setattr(onboarding_vault, "prompt_yes_no", lambda *_: True)
    monkeypatch.setattr(onboarding_telegram, "prompt_yes_no", lambda *_: True)
    monkeypatch.setattr(onboarding_vault.getpass, "getpass", lambda *_: "secret")
    stored: list[dict[str, str]] = []

    def fake_create(vault: str, title: str, secret: str) -> bool:
        stored.append({"vault": vault, "title": title, "secret": secret})
        return True

    monkeypatch.setattr(onboarding_vault, "create_onepassword_item", fake_create)
    monkeypatch.setattr(onboarding_vault, "ensure_onepassword_vault", lambda *_: True)
    monkeypatch.setattr(
        onboarding_telegram, "_fetch_bot_username_from_token", lambda *_: None
    )

    onboarding_telegram.offer_optional_telegram_setup()
    captured = capsys.readouterr().out
    assert "Telegram" in captured and "t.me/BotFather" in captured
    assert "QR" in captured
    titles = {entry["title"] for entry in stored}
    assert "TELEGRAM_BOT_TOKEN" in titles
    assert "TELEGRAM_BOT_USERNAME" in titles
    assert "TELEGRAM_WEBHOOK_SECRET" in titles


def test_optional_telegram_setup_skips_prompt_when_found_in_1password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(onboarding_telegram.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(
        onboarding_telegram,
        "_load_secret_from_1password",
        lambda *_args, **_kwargs: "token",
    )

    webhook_called: list[bool] = []

    def _mark_webhook_called() -> None:
        webhook_called.append(True)

    def _fail_store(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError(
            "Should not prompt to store token when found in 1Password."
        )

    monkeypatch.setattr(
        onboarding_telegram,
        "_offer_optional_telegram_webhook_setup",
        _mark_webhook_called,
    )
    monkeypatch.setattr(
        onboarding_telegram, "prompt_store_secret_in_1password", _fail_store
    )
    onboarding_telegram.offer_optional_telegram_setup()
    assert webhook_called


def test_check_docker_socket_access_denied(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    socket_path = tmp_path / "docker.sock"
    socket_path.write_text("", encoding="utf-8")
    socket_path.chmod(0)
    monkeypatch.setenv("DOCKER_HOST", f"unix://{socket_path}")
    monkeypatch.setattr(onboarding_docker, "skills_require_docker", lambda: True)
    monkeypatch.setattr(onboarding_docker.shutil, "which", lambda *_: "/usr/bin/docker")

    assert onboarding_docker.check_docker_socket_access() is False
    captured = capsys.readouterr().out
    assert "Docker socket is not accessible" in captured


def test_check_docker_socket_access_remote_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCKER_HOST", "tcp://127.0.0.1:2375")
    monkeypatch.setattr(onboarding_docker, "skills_require_docker", lambda: True)
    monkeypatch.setattr(onboarding_docker.shutil, "which", lambda *_: "/usr/bin/docker")

    assert onboarding_docker.check_docker_socket_access() is True


def test_prompt_store_secret_requires_write_access(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class DummyResult:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd: list[str], **kwargs) -> DummyResult:  # noqa: ANN001
        if cmd[:3] == ["op", "item", "create"] and "--format" in cmd:
            return DummyResult(returncode=1, stderr="You do not have permission")
        if cmd[:3] == ["op", "vault", "get"]:
            return DummyResult(returncode=0)
        return DummyResult(returncode=0)

    monkeypatch.setattr(onboarding_vault.shutil, "which", lambda *_: "/usr/bin/op")
    monkeypatch.setattr(onboarding_vault, "has_onepassword_auth", lambda: True)

    def _fail_prompt(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("Prompt should not be called without write access.")

    monkeypatch.setattr(onboarding_vault, "prompt_yes_no", _fail_prompt)
    monkeypatch.setattr(onboarding_vault.getpass, "getpass", lambda *_: "secret")
    monkeypatch.setattr(onboarding_vault.subprocess, "run", fake_run)

    assert (
        onboarding_cli.prompt_store_secret_in_1password(
            env_name="BRAVE_API_KEY",
            description="Brave Search API key",
            doc_hint=None,
            vault_name="CyberneticAgents",
        )
        is False
    )
    captured = capsys.readouterr().out
    assert "write access" in captured.lower()


def test_loads_brave_key_from_onepassword(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)
    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/op")

    def _load_secret(**_kwargs: object) -> str:
        return "brave-secret"

    monkeypatch.setattr(onboarding_cli, "_load_secret_from_1password", _load_secret)
    assert onboarding_cli._check_required_tool_secrets() is True
    captured = capsys.readouterr().out
    assert "✓ Web search is now available." in captured


def test_check_network_access_fails_when_required(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    skill = SkillDefinition(
        name="web-search",
        description="Search the web",
        location=Path("src/tools/skills/web-search"),
        tool_name="web_search",
        subcommand=None,
        required_env=("BRAVE_API_KEY",),
        timeout_class="short",
        timeout_seconds=30,
        input_schema={},
        output_schema={},
        skill_file=Path("src/tools/skills/web-search/SKILL.md"),
        instructions="",
    )
    monkeypatch.setattr(onboarding_cli, "load_skill_definitions", lambda *_: [skill])
    monkeypatch.setattr(onboarding_cli, "_probe_network_access", lambda: False)

    assert onboarding_cli._check_network_access() is False
    captured = capsys.readouterr().out
    assert "Network access is required" in captured


def test_check_network_access_skips_without_network_skills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill = SkillDefinition(
        name="file-reader",
        description="Read local files",
        location=Path("src/tools/skills/file-reader"),
        tool_name="file_reader",
        subcommand=None,
        required_env=(),
        timeout_class="short",
        timeout_seconds=30,
        input_schema={},
        output_schema={},
        skill_file=Path("src/tools/skills/file-reader/SKILL.md"),
        instructions="",
    )
    monkeypatch.setattr(onboarding_cli, "load_skill_definitions", lambda *_: [skill])

    def _fail_probe() -> bool:
        raise AssertionError("Network probe should not run.")

    monkeypatch.setattr(onboarding_cli, "_probe_network_access", _fail_probe)
    assert onboarding_cli._check_network_access() is True


def test_warn_optional_api_keys_reads_onepassword(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    optional_keys = [
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGSMITH_API_KEY",
    ]
    for key in optional_keys:
        monkeypatch.delenv(key, raising=False)

    def _load_secret(
        *, vault_name: str, item_name: str, field_label: str
    ) -> str | None:
        if item_name in {"LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"}:
            return "secret"
        return None

    monkeypatch.setattr(onboarding_optional, "load_secret_from_1password", _load_secret)

    onboarding_cli._warn_optional_api_keys()
    captured = capsys.readouterr().out
    assert "LANGSMITH_API_KEY" in captured
    assert "LANGFUSE_PUBLIC_KEY" not in captured
    assert "LANGFUSE_SECRET_KEY" not in captured


def test_check_onboarding_repo_token_warns_when_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITHUB_READONLY_TOKEN", raising=False)
    monkeypatch.setattr(
        onboarding_cli,
        "load_secret_from_1password_with_error",
        lambda **_kwargs: (None, None),
    )

    assert onboarding_cli._check_onboarding_repo_token() is True
    captured = capsys.readouterr().out
    assert "GITHUB_READONLY_TOKEN" in captured
