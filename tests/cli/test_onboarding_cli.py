from __future__ import annotations

import argparse
from pathlib import Path
import pytest

from src.cyberagent.cli import onboarding as onboarding_cli
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.procedure import Procedure
from src.cyberagent.db.models.procedure_run import ProcedureRun
from src.cyberagent.db.models.procedure_task import ProcedureTask
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import teams as teams_service
from src.cyberagent.tools.cli_executor.skill_loader import SkillDefinition
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


def test_handle_onboarding_creates_default_team(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_teams()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)

    exit_code = onboarding_cli.handle_onboarding(
        argparse.Namespace(), 'cyberagent suggest "Describe the task"'
    )
    captured = capsys.readouterr().out
    monkeypatch.undo()

    assert exit_code == 0
    assert "Created default team" in captured
    assert "cyberagent suggest" in captured

    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == "root").first()
        assert team is not None
    finally:
        session.close()


def test_handle_onboarding_skips_when_team_exists(
    capsys: pytest.CaptureFixture[str],
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
    exit_code = onboarding_cli.handle_onboarding(
        argparse.Namespace(), 'cyberagent suggest "Describe the task"'
    )
    captured = capsys.readouterr().out
    monkeypatch.undo()

    assert exit_code == 0
    assert "Team already exists" in captured
    assert "cyberagent suggest" in captured

    session = next(get_db())
    try:
        assert session.query(Team).count() == 1
    finally:
        session.close()


def test_handle_onboarding_requires_technical_checks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _clear_teams()

    monkeypatch.setattr(
        onboarding_cli, "run_technical_onboarding_checks", lambda: False
    )

    exit_code = onboarding_cli.handle_onboarding(
        argparse.Namespace(), 'cyberagent suggest "Describe the task"'
    )
    captured = capsys.readouterr().out

    assert exit_code == 1
    assert "technical onboarding" in captured.lower()


def test_handle_onboarding_seeds_default_sops(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_teams()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)

    exit_code = onboarding_cli.handle_onboarding(
        argparse.Namespace(), 'cyberagent suggest "Describe the task"'
    )
    captured = capsys.readouterr().out
    monkeypatch.undo()

    assert exit_code == 0
    assert "cyberagent suggest" in captured

    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == "root").first()
        assert team is not None
        procedures = session.query(Procedure).filter(Procedure.team_id == team.id).all()
        procedure_names = {procedure.name for procedure in procedures}
        assert procedure_names == {
            "First Run Discovery",
            "Purpose Adjustment Review",
            "Product Discovery Research Loop",
        }
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


def test_handle_onboarding_sets_root_team_envelope() -> None:
    _clear_teams()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)

    onboarding_cli.handle_onboarding(
        argparse.Namespace(), 'cyberagent suggest "Describe the task"'
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


def test_handle_onboarding_seeds_default_sops_once() -> None:
    _clear_teams()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(onboarding_cli, "run_technical_onboarding_checks", lambda: True)

    onboarding_cli.handle_onboarding(
        argparse.Namespace(), 'cyberagent suggest "Describe the task"'
    )
    onboarding_cli.handle_onboarding(
        argparse.Namespace(), 'cyberagent suggest "Describe the task"'
    )
    monkeypatch.undo()

    session = next(get_db())
    try:
        team = session.query(Team).filter(Team.name == "root").first()
        assert team is not None
        count = session.query(Procedure).filter(Procedure.team_id == team.id).count()
        assert count == 3
    finally:
        session.close()


def test_technical_onboarding_requires_groq_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setattr(onboarding_cli, "_is_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "_check_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "_check_docker_socket_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_docker_available", lambda: True)
    monkeypatch.setattr(
        onboarding_cli, "_check_cli_tools_image_available", lambda: True
    )
    monkeypatch.setattr(onboarding_cli, "_check_skill_root_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_network_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_required_tool_secrets", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)
    monkeypatch.setattr(
        onboarding_cli, "_load_technical_onboarding_state", lambda: None
    )
    monkeypatch.setattr(
        onboarding_cli, "_save_technical_onboarding_state", lambda *_: None
    )
    monkeypatch.setattr(onboarding_cli, "_prompt_yes_no", lambda *_: False)

    assert onboarding_cli.run_technical_onboarding_checks() is False
    captured = capsys.readouterr().out
    assert "GROQ_API_KEY" in captured


def test_technical_onboarding_requires_onepassword_auth(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setattr(onboarding_cli, "_is_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "_check_path_writable", lambda *_: True)
    monkeypatch.setattr(onboarding_cli, "_check_docker_socket_access", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_check_docker_available", lambda: True)
    monkeypatch.setattr(
        onboarding_cli, "_check_cli_tools_image_available", lambda: True
    )
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


def test_missing_brave_key_explains_vault_and_item(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)
    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/op")

    def _load_secret(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(onboarding_cli, "_load_secret_from_1password", _load_secret)
    monkeypatch.setattr(onboarding_cli, "_prompt_yes_no", lambda *_: False)

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

    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/op")
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)
    monkeypatch.setattr(onboarding_cli, "_prompt_yes_no", lambda *_: True)
    monkeypatch.setattr(onboarding_cli.getpass, "getpass", lambda *_: "secret")
    monkeypatch.setattr(onboarding_cli.subprocess, "run", fake_run)

    assert (
        onboarding_cli._prompt_store_secret_in_1password(
            env_name="BRAVE_API_KEY",
            description="Brave Search API key",
            doc_hint=None,
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
    monkeypatch.setattr(onboarding_cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/op")
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)
    monkeypatch.setattr(
        onboarding_cli, "_check_onepassword_write_access", lambda *_: True
    )
    monkeypatch.setattr(onboarding_cli, "_prompt_yes_no", lambda *_: True)
    monkeypatch.setattr(onboarding_cli.getpass, "getpass", lambda *_: "secret")

    stored: list[dict[str, str]] = []

    def fake_create(vault: str, title: str, secret: str) -> bool:
        stored.append({"vault": vault, "title": title, "secret": secret})
        return True

    monkeypatch.setattr(onboarding_cli, "_create_onepassword_item", fake_create)
    monkeypatch.setattr(onboarding_cli, "_ensure_onepassword_vault", lambda *_: True)

    onboarding_cli._offer_optional_telegram_setup()
    captured = capsys.readouterr().out
    assert "Telegram" in captured
    titles = {entry["title"] for entry in stored}
    assert "TELEGRAM_BOT_TOKEN" in titles
    assert "TELEGRAM_WEBHOOK_SECRET" in titles


def test_check_docker_socket_access_denied(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    socket_path = tmp_path / "docker.sock"
    socket_path.write_text("", encoding="utf-8")
    socket_path.chmod(0)
    monkeypatch.setenv("DOCKER_HOST", f"unix://{socket_path}")
    monkeypatch.setattr(onboarding_cli, "_skills_require_docker", lambda: True)
    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/docker")

    assert onboarding_cli._check_docker_socket_access() is False
    captured = capsys.readouterr().out
    assert "Docker socket is not accessible" in captured


def test_check_docker_socket_access_remote_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCKER_HOST", "tcp://127.0.0.1:2375")
    monkeypatch.setattr(onboarding_cli, "_skills_require_docker", lambda: True)
    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/docker")

    assert onboarding_cli._check_docker_socket_access() is True


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

    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/op")
    monkeypatch.setattr(onboarding_cli, "_has_onepassword_auth", lambda: True)

    def _fail_prompt(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("Prompt should not be called without write access.")

    monkeypatch.setattr(onboarding_cli, "_prompt_yes_no", _fail_prompt)
    monkeypatch.setattr(onboarding_cli.getpass, "getpass", lambda *_: "secret")
    monkeypatch.setattr(onboarding_cli.subprocess, "run", fake_run)

    assert (
        onboarding_cli._prompt_store_secret_in_1password(
            env_name="BRAVE_API_KEY",
            description="Brave Search API key",
            doc_hint=None,
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
    assert "Found BRAVE_API_KEY" in captured


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


def test_check_docker_optional_when_no_skills(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(onboarding_cli, "load_skill_definitions", lambda *_: [])
    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: None)

    assert onboarding_cli._check_docker_available() is True
    captured = capsys.readouterr().out
    assert "Continuing without tool execution" in captured


def test_check_cli_tools_image_available_missing(
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
    monkeypatch.setattr(onboarding_cli.shutil, "which", lambda *_: "/usr/bin/docker")

    class DummyResult:
        def __init__(self, returncode: int) -> None:
            self.returncode = returncode
            self.stdout = ""
            self.stderr = ""

    def fake_run(*_args: object, **_kwargs: object) -> DummyResult:
        return DummyResult(returncode=1)

    monkeypatch.setattr(onboarding_cli.subprocess, "run", fake_run)

    assert onboarding_cli._check_cli_tools_image_available() is False
    captured = capsys.readouterr().out
    assert "CLI tools image is not available" in captured


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

    monkeypatch.setattr(onboarding_cli, "_load_secret_from_1password", _load_secret)

    onboarding_cli._warn_optional_api_keys()
    captured = capsys.readouterr().out
    assert "LANGSMITH_API_KEY" in captured
    assert "LANGFUSE_PUBLIC_KEY" not in captured
    assert "LANGFUSE_SECRET_KEY" not in captured
