from __future__ import annotations

import argparse
from datetime import datetime
import json
import shutil
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

from sqlalchemy.exc import SQLAlchemyError

from src.cyberagent.cli.agent_message_queue import enqueue_agent_message
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import get_database_path, init_db
from src.cyberagent.db.models.procedure import Procedure
from src.cyberagent.db.models.procedure_run import ProcedureRun
from src.cyberagent.db.models.strategy import Strategy
from src.cyberagent.db.models.system import System
from src.cyberagent.db.models.system import ensure_default_systems_for_team
from src.cyberagent.db.models.system import get_system_by_type
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import procedures as procedures_service
from src.cyberagent.services import purposes as purposes_service
from src.cyberagent.services import strategies as strategies_service
from src.cyberagent.services import systems as systems_service
from src.cyberagent.services import teams as teams_service
from src.cyberagent.tools.cli_executor.skill_loader import (
    SkillDefinition,
    load_skill_definitions,
)
from src.cyberagent.cli.onboarding_docker import (
    check_cli_tools_image_available,
    check_docker_available,
    check_docker_socket_access,
)
from src.cyberagent.tools.cli_executor.skill_runtime import DEFAULT_SKILLS_ROOT
from src.cyberagent.cli.onboarding_defaults import (
    load_procedure_defaults,
    load_root_team_defaults,
)
from src.cyberagent.cli.onboarding_discovery import run_discovery_onboarding
from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.onboarding_constants import DEFAULT_GIT_TOKEN_ENV
from src.cyberagent.cli.onboarding_secrets import (
    VAULT_NAME,
    get_onepassword_session_env,
    has_onepassword_auth,
    load_secret_from_1password,
    load_secret_from_1password_with_error,
)
from src.cyberagent.cli.onboarding_vault import (
    prompt_store_secret_in_1password,
    prompt_yes_no,
)
from src.cyberagent.cli.onboarding_memory import store_onboarding_memory
from src.enums import SystemType

LOGS_DIR = Path("logs")
TECH_ONBOARDING_STATE_FILE = Path("logs/technical_onboarding.json")
RUNTIME_PID_FILE = Path("logs/cyberagent.pid")
NETWORK_SKILL_NAMES = {"web-fetch", "web-search", "git-readonly-sync"}
TOOL_SECRET_DOC_HINTS = {
    "BRAVE_API_KEY": "src/tools/skills/web-search/SKILL.md",
}
TELEGRAM_DOC_HINT = "docs/technical/telegram_setup.md"
FEATURE_READY_MESSAGE_KEYS = {
    "BRAVE_API_KEY": "feature_web_search",
    "GROQ_API_KEY": "feature_ai_ready",
    "MISTRAL_API_KEY": "feature_ai_ready",
    "TELEGRAM_BOT_TOKEN": "feature_telegram",
}


def handle_onboarding(args: argparse.Namespace, suggest_command: str) -> int:
    if not run_technical_onboarding_checks():
        print(get_message("onboarding", "technical_checks_failed"))
        return 1
    if not _validate_onboarding_inputs(args):
        return 1
    procedures = load_procedure_defaults()
    team_defaults = load_root_team_defaults()
    team_name = _get_default_team_name(team_defaults)
    purpose_name = _get_default_purpose_name(team_defaults)
    strategy_name = _get_default_strategy_name(team_defaults)
    auto_execute = _get_auto_execute_procedure(team_defaults, procedures)
    init_db()
    session = next(get_db())
    try:
        team = session.query(Team).order_by(Team.id).first()
        if team is None:
            team = Team(name=team_name, last_active_at=datetime.utcnow())
            session.add(team)
            session.commit()
            print(
                get_message(
                    "onboarding",
                    "team_created",
                    team_name=team.name,
                    team_id=team.id,
                )
            )
        else:
            print(
                get_message(
                    "onboarding",
                    "team_exists",
                    team_name=team.name,
                    team_id=team.id,
                )
            )
    finally:
        session.close()
    _seed_default_team_envelope(team.id, team_defaults)
    _ensure_team_systems(team.id, team_defaults)
    _seed_default_procedures(team.id, procedures)
    print(get_message("onboarding", "discovery_starting"))
    summary_path = _run_discovery_onboarding(args, team.id)
    if summary_path is None:
        print(get_message("onboarding", "discovery_failed"))
        print(get_message("onboarding", "discovery_failed_hint"))
        return 1
    store_onboarding_memory(team.id, summary_path)
    if auto_execute:
        if not _trigger_onboarding_initiative(
            team.id,
            onboarding_procedure_name=auto_execute,
            onboarding_strategy_name=strategy_name,
            onboarding_purpose_name=purpose_name,
        ):
            return 1
    _start_runtime_after_onboarding(team.id)
    print(get_message("onboarding", "next_suggest", suggest_command=suggest_command))
    return 0


def _validate_onboarding_inputs(args: argparse.Namespace) -> bool:
    _prompt_for_missing_inputs(args)
    user_name = getattr(args, "user_name", None)
    repo_url = getattr(args, "repo_url", None)
    if not user_name:
        print(get_message("onboarding", "onboarding_needs_name"))
        return False
    if not repo_url:
        print(get_message("onboarding", "onboarding_needs_repo"))
        return False
    return True


def _prompt_for_missing_inputs(args: argparse.Namespace) -> None:
    user_name = str(getattr(args, "user_name", "") or "").strip()
    if not user_name:
        print(get_message("onboarding", "onboarding_welcome"))
        user_name = _prompt_required_value(
            get_message("onboarding", "onboarding_prompt_user_name")
        )
        setattr(args, "user_name", user_name)

    repo_url = str(getattr(args, "repo_url", "") or "").strip()
    if not repo_url:
        repo_url = _prompt_required_value(
            get_message("onboarding", "onboarding_prompt_repo")
        )
        setattr(args, "repo_url", repo_url)

    profile_links = list(getattr(args, "profile_links", []) or [])
    if not profile_links:
        raw_links = input(
            get_message("onboarding", "onboarding_prompt_profile_links")
        ).strip()
        if raw_links:
            links = [link.strip() for link in raw_links.split(",") if link.strip()]
            if links:
                setattr(args, "profile_links", links)


def _prompt_required_value(prompt: str) -> str:
    while True:
        value = input(f"{prompt}: ").strip()
        if value:
            return value
        print(get_message("onboarding", "onboarding_missing_value"))


def _start_runtime_after_onboarding(team_id: int) -> int | None:
    if os.environ.get("CYBERAGENT_TEST_NO_RUNTIME") == "1":
        return None
    pid = _load_runtime_pid()
    if pid is not None and _pid_is_running(pid):
        print(get_message("onboarding", "runtime_already_running", pid=pid))
        return pid
    cmd = [sys.executable, "-m", "src.cyberagent.cli.cyberagent", "serve"]
    env = os.environ.copy()
    env["CYBERAGENT_ACTIVE_TEAM_ID"] = str(team_id)
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    RUNTIME_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    print(get_message("onboarding", "runtime_starting", pid=proc.pid))
    return proc.pid


def _get_default_team_name(team_defaults: dict[str, object]) -> str:
    team_block = team_defaults.get("team")
    if isinstance(team_block, dict):
        name = team_block.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return "root"


def _get_default_purpose_name(team_defaults: dict[str, object]) -> str:
    purpose = team_defaults.get("purpose")
    if isinstance(purpose, dict):
        name = purpose.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return "Onboarding SOP"


def _get_default_strategy_name(team_defaults: dict[str, object]) -> str:
    strategy = team_defaults.get("strategy")
    if isinstance(strategy, dict):
        name = strategy.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return "Onboarding SOP"


def _get_auto_execute_procedure(
    team_defaults: dict[str, object], procedures: list[dict[str, object]]
) -> str | None:
    value = team_defaults.get("auto_execute_procedure")
    if isinstance(value, str) and value.strip():
        return value.strip()
    listed = team_defaults.get("procedures")
    if isinstance(listed, list) and listed:
        first = listed[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    if procedures:
        first_name = procedures[0].get("name")
        if isinstance(first_name, str) and first_name.strip():
            return first_name.strip()
    return None


def _seed_default_procedures(team_id: int, procedures: list[dict[str, object]]) -> None:
    ensure_default_systems_for_team(team_id)
    system4 = get_system_by_type(team_id, SystemType.INTELLIGENCE)
    system5 = get_system_by_type(team_id, SystemType.POLICY)

    session = next(get_db())
    try:
        existing_names = {
            procedure.name
            for procedure in session.query(Procedure)
            .filter(Procedure.team_id == team_id)
            .all()
        }
    finally:
        session.close()

    for template in procedures:
        name = template.get("name")
        if not isinstance(name, str):
            continue
        if name in existing_names:
            continue
        tasks = template.get("tasks")
        if not isinstance(tasks, list):
            tasks = []
        procedure = procedures_service.create_procedure_draft(
            team_id=team_id,
            name=name,
            description=str(template.get("description", "")),
            risk_level=str(template.get("risk_level", "")),
            impact=str(template.get("impact", "")),
            rollback_plan=str(template.get("rollback_plan", "")),
            created_by_system_id=system4.id,
            tasks=tasks,
        )
        procedures_service.approve_procedure(
            procedure_id=procedure.id, approved_by_system_id=system5.id
        )


def _seed_default_team_envelope(team_id: int, team_defaults: dict[str, object]) -> None:
    allowed = team_defaults.get("allowed_skills")
    if not isinstance(allowed, list):
        return
    skill_names = [skill for skill in allowed if isinstance(skill, str)]
    teams_service.set_allowed_skills(team_id, skill_names, actor_id="onboarding")


def _ensure_team_systems(team_id: int, team_defaults: dict[str, object]) -> None:
    systems_block = team_defaults.get("systems")
    if not isinstance(systems_block, list):
        ensure_default_systems_for_team(team_id)
        return
    session = next(get_db())
    try:
        existing = {
            system.type: system
            for system in session.query(System).filter(System.team_id == team_id).all()
        }
        for entry in systems_block:
            if not isinstance(entry, dict):
                continue
            type_value = entry.get("type")
            name = entry.get("name")
            agent_id = entry.get("agent_id")
            if not isinstance(type_value, str):
                continue
            try:
                system_type = SystemType[type_value]
            except KeyError:
                continue
            if system_type in existing:
                continue
            if not isinstance(name, str) or not isinstance(agent_id, str):
                continue
            system = System(
                team_id=team_id,
                name=name,
                type=system_type,
                agent_id_str=agent_id,
            )
            session.add(system)
            existing[system_type] = system
        session.commit()
    finally:
        session.close()

    for entry in systems_block:
        if not isinstance(entry, dict):
            continue
        type_value = entry.get("type")
        if not isinstance(type_value, str):
            continue
        try:
            system_type = SystemType[type_value]
        except KeyError:
            continue
        systems = (
            systems_service.get_systems_by_type(team_id, system_type)
            if system_type == SystemType.OPERATION
            else [get_system_by_type(team_id, system_type)]
        )
        skill_grants = entry.get("skill_grants")
        if not isinstance(skill_grants, list):
            continue
        for system in systems:
            for skill_name in skill_grants:
                if isinstance(skill_name, str):
                    systems_service.add_skill_grant(
                        system.id, skill_name, actor_id="onboarding"
                    )


def _build_onboarding_prompt(summary_path: Path, summary_text: str) -> str:
    from src.cyberagent.cli.onboarding_discovery import build_onboarding_prompt

    return build_onboarding_prompt(summary_path=summary_path, summary_text=summary_text)


def _run_discovery_onboarding(args: argparse.Namespace, team_id: int) -> Path | None:
    del team_id
    return run_discovery_onboarding(args)


def _trigger_onboarding_initiative(
    team_id: int,
    onboarding_procedure_name: str,
    onboarding_strategy_name: str,
    onboarding_purpose_name: str,
) -> bool:
    ensure_default_systems_for_team(team_id)
    session = next(get_db())
    try:
        procedure = (
            session.query(Procedure)
            .filter(
                Procedure.team_id == team_id,
                Procedure.name == onboarding_procedure_name,
            )
            .first()
        )
    finally:
        session.close()
    if procedure is None:
        return True
    session = next(get_db())
    try:
        existing_run = (
            session.query(ProcedureRun)
            .filter(ProcedureRun.procedure_id == procedure.id)
            .first()
        )
    finally:
        session.close()
    if existing_run is not None:
        return True

    purpose = purposes_service.get_or_create_default_purpose(team_id)
    purpose.name = onboarding_purpose_name
    purpose.content = procedure.description
    try:
        purpose.update()
    except SQLAlchemyError as exc:
        _print_db_write_error("purpose", exc)
        return False

    session = next(get_db())
    try:
        strategy = (
            session.query(Strategy)
            .filter(
                Strategy.team_id == team_id,
                Strategy.name == onboarding_strategy_name,
            )
            .first()
        )
    finally:
        session.close()
    if strategy is None:
        try:
            strategy = strategies_service.create_strategy(
                team_id=team_id,
                purpose_id=purpose.id,
                name=onboarding_strategy_name,
                description=procedure.description,
            )
        except SQLAlchemyError as exc:
            _print_db_write_error("strategy", exc)
            return False

    system3 = get_system_by_type(team_id, SystemType.CONTROL)
    if system3 is None:
        return False
    try:
        run = procedures_service.execute_procedure(
            procedure_id=procedure.id,
            team_id=team_id,
            strategy_id=strategy.id,
            executed_by_system_id=system3.id,
        )
    except SQLAlchemyError as exc:
        _print_db_write_error("procedure run", exc)
        return False
    enqueue_agent_message(
        recipient="System3/root",
        sender="System4/root",
        message_type="initiative_assign",
        payload={
            "initiative_id": run.initiative_id,
            "source": "Onboarding",
            "content": f"Start onboarding initiative {run.initiative_id}.",
        },
    )
    return True


def _print_db_write_error(context: str, exc: SQLAlchemyError) -> None:
    db_path = get_database_path()
    message = str(exc).lower()
    hint = get_message("onboarding", "db_write_hint_default")
    if "disk i/o" in message:
        hint = get_message("onboarding", "db_write_hint_disk_io")
    location = "in-memory database" if db_path == ":memory:" else db_path
    print(
        get_message(
            "onboarding",
            "db_write_failed",
            context=context,
            location=location,
        )
    )
    print(get_message("onboarding", "db_write_hint", hint=hint))


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _load_runtime_pid() -> int | None:
    if not RUNTIME_PID_FILE.exists():
        return None
    try:
        return int(RUNTIME_PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def run_technical_onboarding_checks() -> bool:
    state = _collect_technical_onboarding_state()
    cached = _load_technical_onboarding_state()
    if cached and cached.get("state") == state and cached.get("ok") is True:
        print(get_message("onboarding", "technical_already_verified"))
        return True

    if not _check_db_writable():
        return False
    if not _check_logs_writable():
        return False
    print(get_message("onboarding", "activating_features"))

    checks = [
        _check_llm_credentials,
        check_docker_socket_access,
        check_docker_available,
        check_cli_tools_image_available,
        _check_onepassword_auth,
        _check_onboarding_repo_token,
        _check_required_tool_secrets,
        _check_skill_root_access,
        _check_network_access,
    ]
    for check in checks:
        if not check():
            return False

    _warn_optional_api_keys()
    _offer_optional_telegram_setup()
    _save_technical_onboarding_state({"state": state, "ok": True})
    print(get_message("onboarding", "technical_checks_passed"))
    return True


def _collect_technical_onboarding_state() -> dict[str, object]:
    llm_provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    return {
        "llm_provider": llm_provider,
        "has_groq_key": bool(os.environ.get("GROQ_API_KEY")),
        "has_mistral_key": bool(os.environ.get("MISTRAL_API_KEY")),
        "has_brave_key": bool(os.environ.get("BRAVE_API_KEY")),
        "has_langfuse_public": bool(os.environ.get("LANGFUSE_PUBLIC_KEY")),
        "has_langfuse_secret": bool(os.environ.get("LANGFUSE_SECRET_KEY")),
        "has_langsmith": bool(os.environ.get("LANGSMITH_API_KEY")),
        "has_telegram_token": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "has_telegram_webhook_secret": bool(os.environ.get("TELEGRAM_WEBHOOK_SECRET")),
        "has_telegram_webhook_url": bool(os.environ.get("TELEGRAM_WEBHOOK_URL")),
        "has_onepassword_auth": has_onepassword_auth(),
        "has_op_session": bool(get_onepassword_session_env()),
        "skills_root_exists": DEFAULT_SKILLS_ROOT.exists(),
        "docker_host": os.environ.get("DOCKER_HOST", ""),
        "docker_path": shutil.which("docker") or "",
        "data_dir_writable": _is_path_writable(Path("data")),
        "logs_dir_writable": _is_path_writable(LOGS_DIR),
    }


def _load_technical_onboarding_state() -> dict[str, object] | None:
    if not TECH_ONBOARDING_STATE_FILE.exists():
        return None
    try:
        return json.loads(TECH_ONBOARDING_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _save_technical_onboarding_state(state: dict[str, object]) -> None:
    TECH_ONBOARDING_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    TECH_ONBOARDING_STATE_FILE.write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _is_path_writable(path: Path) -> bool:
    if path.exists():
        return os.access(path, os.W_OK)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return os.access(path, os.W_OK)


def _check_path_writable(label: str, path: Path) -> bool:
    if _is_path_writable(path):
        return True
    print(
        get_message(
            "onboarding",
            "path_not_writable",
            label=label,
            path=path,
        )
    )
    print(get_message("onboarding", "fix_permissions_rerun"))
    return False


def _check_db_writable() -> bool:
    db_path = get_database_path()
    if db_path == ":memory:":
        return True
    db_file = Path(db_path)
    if not _check_path_writable("Database directory", db_file.parent):
        return False
    if db_file.exists() and not os.access(db_file, os.W_OK):
        print(
            get_message(
                "onboarding",
                "database_file_not_writable",
                path=db_file,
            )
        )
        print(get_message("onboarding", "fix_permissions_rerun"))
        return False
    return True


def _check_logs_writable() -> bool:
    return _check_path_writable("Logs directory", LOGS_DIR)


def _format_skill_names(skills: list[str]) -> str:
    readable = []
    for skill in skills:
        label = skill.replace("-", " ").replace("_", " ").strip()
        if label:
            readable.append(label.title())
    return ", ".join(sorted(set(readable)))


def _print_feature_ready(env_name: str, skills: list[str] | None = None) -> None:
    message_key = FEATURE_READY_MESSAGE_KEYS.get(env_name)
    message = get_message("onboarding", message_key) if message_key else None
    if not message and skills:
        skill_names = _format_skill_names(skills)
        if skill_names:
            message = get_message(
                "onboarding", "feature_skills_ready", skill_names=skill_names
            )
    if not message:
        return
    print(get_message("onboarding", "feature_ready", message=message))


def _check_llm_credentials() -> bool:
    if not os.environ.get("GROQ_API_KEY"):
        loaded = _load_secret_from_1password(
            vault_name=VAULT_NAME,
            item_name="GROQ_API_KEY",
            field_label="credential",
        )
        if loaded:
            _print_feature_ready("GROQ_API_KEY")
            return True
        print(get_message("onboarding", "missing_groq"))
        print(
            get_message(
                "onboarding",
                "llm_key_hint",
                vault_name=VAULT_NAME,
                key_name="GROQ_API_KEY",
            )
        )
        print(get_message("onboarding", "field_name_hint"))
        if not prompt_store_secret_in_1password(
            env_name="GROQ_API_KEY",
            description="Groq API key",
            doc_hint=None,
            vault_name=VAULT_NAME,
        ):
            return False
    _print_feature_ready("GROQ_API_KEY")
    if os.environ.get("LLM_PROVIDER", "groq").lower() == "mistral":
        if not os.environ.get("MISTRAL_API_KEY"):
            loaded = _load_secret_from_1password(
                vault_name=VAULT_NAME,
                item_name="MISTRAL_API_KEY",
                field_label="credential",
            )
            if loaded:
                _print_feature_ready("MISTRAL_API_KEY")
                return True
            print(get_message("onboarding", "missing_mistral"))
            print(
                get_message(
                    "onboarding",
                    "llm_key_hint",
                    vault_name=VAULT_NAME,
                    key_name="MISTRAL_API_KEY",
                )
            )
            print(get_message("onboarding", "field_name_hint"))
            if not prompt_store_secret_in_1password(
                env_name="MISTRAL_API_KEY",
                description="Mistral API key",
                doc_hint=None,
                vault_name=VAULT_NAME,
            ):
                return False
        _print_feature_ready("MISTRAL_API_KEY")
    return True


def _has_onepassword_auth() -> bool:
    return has_onepassword_auth()


def _get_onepassword_session_env() -> str | None:
    return get_onepassword_session_env()


def _check_onepassword_auth() -> bool:
    if _has_onepassword_auth():
        return True
    print(get_message("onboarding", "missing_onepassword_auth"))
    print(get_message("onboarding", "missing_onepassword_auth_hint"))
    return False


def _check_required_tool_secrets() -> bool:
    skills = load_skill_definitions(DEFAULT_SKILLS_ROOT)
    required_env = sorted(
        {env for skill in skills for env in skill.required_env if env}
    )
    if not required_env:
        return True

    required_by_env: dict[str, list[str]] = {}
    for skill in skills:
        for env in skill.required_env:
            required_by_env.setdefault(env, []).append(skill.name)

    for env_name in required_env:
        skills_for_env = required_by_env.get(env_name, [])
        if os.environ.get(env_name):
            _print_feature_ready(env_name, skills_for_env)
            continue
        loaded = _load_secret_from_1password(
            vault_name=VAULT_NAME,
            item_name=env_name,
            field_label="credential",
        )
        if loaded:
            _print_feature_ready(env_name, skills_for_env)
            continue
        skills_list = ", ".join(sorted(required_by_env.get(env_name, [])))
        print(
            get_message(
                "onboarding",
                "missing_tool_secret",
                env_name=env_name,
                skills_list=skills_list,
            )
        )
        print(
            get_message(
                "onboarding",
                "tool_secret_hint",
                vault_name=VAULT_NAME,
                env_name=env_name,
            )
        )
        print(get_message("onboarding", "field_name_hint"))
        doc_hint = TOOL_SECRET_DOC_HINTS.get(env_name)
        if doc_hint:
            print(get_message("onboarding", "see_docs_hint", doc_hint=doc_hint))
        if not prompt_store_secret_in_1password(
            env_name=env_name,
            description=f"{env_name} secret",
            doc_hint=doc_hint,
            vault_name=VAULT_NAME,
        ):
            return False
    return True


def _check_onboarding_repo_token() -> bool:
    token_env = DEFAULT_GIT_TOKEN_ENV
    if os.environ.get(token_env):
        return True
    loaded, error = load_secret_from_1password_with_error(
        vault_name=VAULT_NAME,
        item_name=token_env,
        field_label="credential",
    )
    if loaded:
        os.environ[token_env] = loaded
        return True
    if error:
        print(
            get_message(
                "onboarding",
                "github_token_missing_with_error",
                token_env=token_env,
                error=error,
            )
        )
        return True
    print(
        get_message(
            "onboarding",
            "github_token_missing",
            token_env=token_env,
            vault_name=VAULT_NAME,
        )
    )
    return True


def _check_skill_root_access() -> bool:
    if not DEFAULT_SKILLS_ROOT.exists():
        print(
            get_message(
                "onboarding",
                "skills_root_not_found",
                skills_root=DEFAULT_SKILLS_ROOT,
            )
        )
        return False
    if not os.access(DEFAULT_SKILLS_ROOT, os.R_OK):
        print(
            get_message(
                "onboarding",
                "skills_root_not_readable",
                skills_root=DEFAULT_SKILLS_ROOT,
            )
        )
        return False
    return True


def _check_network_access() -> bool:
    skills = load_skill_definitions(DEFAULT_SKILLS_ROOT)
    if not _skills_require_network(skills):
        return True
    if _probe_network_access():
        return True
    skills_list = ", ".join(
        sorted({skill.name for skill in skills if skill.name in NETWORK_SKILL_NAMES})
    )
    print(get_message("onboarding", "network_access_required", skills_list=skills_list))
    print(get_message("onboarding", "enable_network_rerun"))
    return False


def _skills_require_network(skills: list[SkillDefinition]) -> bool:
    return any(skill.name in NETWORK_SKILL_NAMES for skill in skills)


def _probe_network_access() -> bool:
    try:
        with urllib.request.urlopen("https://example.com", timeout=3) as response:
            return response.status < 500
    except OSError:
        return False


def _warn_optional_api_keys() -> None:
    optional = [
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGSMITH_API_KEY",
    ]
    missing: list[str] = []
    for key in optional:
        if os.environ.get(key):
            continue
        loaded = _load_secret_from_1password(
            vault_name=VAULT_NAME,
            item_name=key,
            field_label="credential",
        )
        if loaded:
            continue
        missing.append(key)
    if missing:
        missing_str = ", ".join(missing)
        print(
            get_message(
                "onboarding",
                "optional_api_keys_missing",
                missing_keys=missing_str,
            )
        )


def _offer_optional_telegram_setup() -> None:
    if not sys.stdin.isatty():
        return
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        _print_feature_ready("TELEGRAM_BOT_TOKEN")
        _offer_optional_telegram_webhook_setup()
        return
    loaded = _load_secret_from_1password(
        vault_name=VAULT_NAME,
        item_name="TELEGRAM_BOT_TOKEN",
        field_label="credential",
    )
    if loaded:
        _print_feature_ready("TELEGRAM_BOT_TOKEN")
        _offer_optional_telegram_webhook_setup()
        return
    print(get_message("onboarding", "telegram_not_configured"))
    if not prompt_store_secret_in_1password(
        env_name="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token",
        doc_hint=TELEGRAM_DOC_HINT,
        vault_name=VAULT_NAME,
    ):
        return
    _offer_optional_telegram_webhook_setup()


def _offer_optional_telegram_webhook_setup() -> None:
    if os.environ.get("TELEGRAM_WEBHOOK_SECRET"):
        return
    print(get_message("onboarding", "webhook_mode_optional"))
    if not prompt_yes_no(get_message("onboarding", "webhook_secret_prompt")):
        print(get_message("onboarding", "setup_guide_hint", doc_hint=TELEGRAM_DOC_HINT))
        return
    prompt_store_secret_in_1password(
        env_name="TELEGRAM_WEBHOOK_SECRET",
        description="Telegram webhook secret",
        doc_hint=TELEGRAM_DOC_HINT,
        vault_name=VAULT_NAME,
    )


def _load_secret_from_1password(
    vault_name: str, item_name: str, field_label: str
) -> str | None:
    return load_secret_from_1password(
        vault_name=vault_name, item_name=item_name, field_label=field_label
    )
