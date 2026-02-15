from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.onboarding_bootstrap import (
    ensure_team_systems as _ensure_team_systems,
    seed_default_procedures as _seed_default_procedures,
    seed_default_team_envelope as _seed_default_team_envelope,
    seed_root_team_envelope_from_defaults as _seed_root_team_envelope_from_defaults,
)
from src.cyberagent.cli.onboarding_constants import DEFAULT_GIT_TOKEN_ENV
from src.cyberagent.cli.onboarding_defaults import (
    get_auto_execute_procedure,
    get_default_strategy_name,
    get_default_team_name,
    load_procedure_defaults,
    load_root_team_defaults,
)
from src.cyberagent.cli.onboarding_discovery import (
    run_discovery_onboarding,
    start_discovery_background,
)
from src.cyberagent.cli.onboarding_docker import (
    check_cli_tools_image_available,
    check_docker_available,
    check_docker_socket_access,
)
from src.cyberagent.cli.onboarding_interview import start_onboarding_interview
from src.cyberagent.cli.onboarding_optional import (
    _offer_optional_telegram_setup,
    _warn_optional_api_keys,
)
from src.cyberagent.cli.onboarding_output import apply_onboarding_output
from src.cyberagent.cli import onboarding_contextual_secrets as technical_context
from src.cyberagent.cli.onboarding_routing import (
    seed_default_routing_rules,
    seed_procedure_routing_rules,
)
from src.cyberagent.cli.onboarding_runtime import (
    load_runtime_pid,
    pid_is_running,
    resolve_runtime_db_url,
    start_dashboard_after_onboarding,
)
from src.cyberagent.cli.onboarding_secrets import (
    VAULT_NAME,
    _parse_env_value,
    get_onepassword_session_env,
    has_onepassword_auth,
    load_secret_from_1password,
    load_secret_from_1password_with_error,
)
from src.cyberagent.cli.onboarding_validation import (
    validate_onboarding_inputs as _validate_onboarding_inputs,
)
from src.cyberagent.cli.onboarding_vault import prompt_store_secret_in_1password
from src.cyberagent.cli.runtime_start_health import process_exited_during_startup
from src.cyberagent.core.paths import get_data_dir, get_logs_dir, get_repo_root
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import (
    DATABASE_URL,
    get_database_path,
    init_db,
    recover_sqlite_database,
)
from src.cyberagent.db.models.team import Team
from src.cyberagent.secrets import get_secret
from src.cyberagent.tools.cli_executor.skill_loader import (
    SkillDefinition,
    load_skill_definitions,
)
from src.cyberagent.tools.cli_executor.skill_runtime import DEFAULT_SKILLS_ROOT

LOGS_DIR = get_logs_dir()
TECH_ONBOARDING_STATE_FILE = LOGS_DIR / "technical_onboarding.json"
RUNTIME_PID_FILE = LOGS_DIR / "cyberagent.pid"
RUNTIME_STARTUP_GRACE_SECONDS = 1.0
NETWORK_SKILL_NAMES = {"web-fetch", "web-search", "git-readonly-sync"}
TOOL_SECRET_DOC_HINTS = {
    "BRAVE_API_KEY": "src/tools/skills/web-search/SKILL.md",
}
FEATURE_READY_MESSAGE_KEYS = {
    "BRAVE_API_KEY": "feature_web_search",
    "GROQ_API_KEY": "feature_ai_ready",
    "MISTRAL_API_KEY": "feature_ai_ready",
    "TELEGRAM_BOT_TOKEN": "feature_telegram",
}
ENV_ROOT_KEY = "CYBERAGENT_ROOT"


def _print_db_write_error(context: str, exc: Exception) -> None:
    db_path = get_database_path()
    message = str(exc).lower()
    hint = get_message("onboarding", "db_write_hint_default")
    if "disk i/o" in message:
        backup_path = recover_sqlite_database()
        if backup_path is not None:
            print(
                get_message("onboarding", "db_recovered_hint", backup_path=backup_path)
            )
        hint = get_message("onboarding", "db_write_hint_disk_io")
    location = "in-memory database" if db_path == ":memory:" else db_path
    print(
        get_message("onboarding", "db_write_failed", context=context, location=location)
    )
    print(get_message("onboarding", "db_write_hint", hint=hint))



def _repo_root() -> Path | None:
    return get_repo_root()


def _ensure_repo_root_env_var() -> None:
    repo_root = _repo_root()
    if repo_root is None:
        return
    env_path = repo_root / ".env"
    repo_root_value = str(repo_root.resolve())
    lines: list[str] = []
    if env_path.exists():
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
    updated = False
    found = False
    for index, line in enumerate(lines):
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        if key.strip() != ENV_ROOT_KEY:
            continue
        found = True
        parsed = _parse_env_value(value)
        if parsed:
            os.environ.setdefault(ENV_ROOT_KEY, parsed)
            return
        lines[index] = f"{ENV_ROOT_KEY}={repo_root_value}"
        updated = True
        break
    if not found:
        lines.append(f"{ENV_ROOT_KEY}={repo_root_value}")
        updated = True
    if updated:
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ.setdefault(ENV_ROOT_KEY, repo_root_value)


def handle_onboarding(
    args: argparse.Namespace, suggest_command: str, inbox_command: str
) -> int:
    _ensure_repo_root_env_var()
    if not _validate_onboarding_inputs(args):
        return 1

    pkm_source = technical_context.normalize_pkm_source(getattr(args, "pkm_source", None))
    if not technical_context.run_technical_checks_with_context(
        run_technical_onboarding_checks,
        pkm_source=pkm_source,
    ):
        print(get_message("onboarding", "technical_checks_failed"))
        return 1

    procedures = load_procedure_defaults()
    team_defaults = load_root_team_defaults()
    team_name = get_default_team_name(team_defaults)
    strategy_name = get_default_strategy_name(team_defaults)
    get_auto_execute_procedure(team_defaults, procedures)
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
    _seed_root_team_envelope_from_defaults(team_defaults)
    _ensure_team_systems(team.id, team_defaults)
    _seed_default_procedures(team.id, procedures)
    seed_default_routing_rules(team.id, team_defaults)
    seed_procedure_routing_rules(team.id, procedures)
    print(get_message("onboarding", "discovery_starting"))
    start_onboarding_interview(
        user_name=str(getattr(args, "user_name", "")).strip(),
        pkm_source=str(getattr(args, "pkm_source", "")).strip(),
        repo_url=str(getattr(args, "repo_url", "")).strip(),
        profile_links=list(getattr(args, "profile_links", []) or []),
    )

    # Phase 1 onboarding requires a persisted onboarding output that can be applied to
    # root context (purpose + strategy).
    #
    # Discovery sometimes prompts for input (PKM/auth decisions). In non-interactive
    # contexts (including test runs), default to background discovery to avoid blocking.
    background_discovery_raw = os.environ.get(
        "CYBERAGENT_ONBOARDING_DISCOVERY_BACKGROUND", ""
    )
    foreground_raw = os.environ.get("CYBERAGENT_ONBOARDING_DISCOVERY_FOREGROUND", "")

    force_foreground = foreground_raw.strip().lower() in {"1", "true", "yes"}
    force_background = background_discovery_raw.strip().lower() in {"1", "true", "yes"}

    if force_foreground:
        background_discovery = False
    elif force_background:
        background_discovery = True
    else:
        # Default to background discovery so onboarding can start immediately.
        # Foreground discovery can take minutes (e.g. PKM repo sync / docker pulls)
        # and shouldn't block the user from answering the first question.
        background_discovery = True

    summary_path: Path | None = None
    if background_discovery:
        start_discovery_background(args, team.id)
    else:
        summary_path = run_discovery_onboarding(args, team.id)
        if summary_path is None:
            print(get_message("onboarding", "discovery_failed"))
            print(get_message("onboarding", "discovery_failed_hint"))
            return 1

    if summary_path is not None:
        apply_onboarding_output(
            team_id=team.id,
            summary_path=summary_path,
            onboarding_strategy_name=strategy_name,
        )

    # Phase 1 scope explicitly avoids creating System3 initiatives/tasks. The SOP is
    # still seeded/approved for later execution, but not auto-executed during onboarding.
    runtime_pid = _start_runtime_after_onboarding(team.id)
    if runtime_pid == -1:
        return 1
    print(get_message("onboarding", "next_suggest", suggest_command=suggest_command))
    start_dashboard_after_onboarding(team.id)
    return 0


def _start_runtime_after_onboarding(team_id: int) -> int | None:
    if os.environ.get("CYBERAGENT_TEST_NO_RUNTIME") == "1":
        return None
    pid = load_runtime_pid(RUNTIME_PID_FILE)
    if pid is not None and pid_is_running(pid):
        print(get_message("onboarding", "runtime_already_running", pid=pid))
        return pid
    cmd = [sys.executable, "-m", "src.cyberagent.cli.cyberagent", "serve"]
    env = os.environ.copy()
    env["CYBERAGENT_ACTIVE_TEAM_ID"] = str(team_id)
    env["CYBERAGENT_DB_URL"] = resolve_runtime_db_url(
        DATABASE_URL, get_database_path()
    )
    telegram_token = get_secret("TELEGRAM_BOT_TOKEN")
    if telegram_token:
        env["TELEGRAM_BOT_TOKEN"] = telegram_token
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    returncode = process_exited_during_startup(proc, RUNTIME_STARTUP_GRACE_SECONDS)
    if returncode is not None:
        try:
            RUNTIME_PID_FILE.unlink()
        except OSError:
            pass
        print(
            get_message(
                "onboarding",
                "runtime_start_failed",
                returncode=returncode,
            )
        )
        print(get_message("onboarding", "runtime_start_failed_hint"))
        return -1
    RUNTIME_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    print(get_message("onboarding", "runtime_starting", pid=proc.pid))
    return proc.pid


def run_technical_onboarding_checks(*, pkm_source: str | None = None) -> bool:
    normalized_pkm_source = technical_context.normalize_pkm_source(pkm_source)
    state = _collect_technical_onboarding_state(pkm_source=normalized_pkm_source)
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
        lambda: _check_required_tool_secrets(pkm_source=normalized_pkm_source),
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


def _collect_technical_onboarding_state(*, pkm_source: str | None = None) -> dict[str, object]:
    llm_provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    return {
        "llm_provider": llm_provider,
        "pkm_source": pkm_source or "unknown",
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
        "data_dir_writable": _is_path_writable(get_data_dir()),
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


_has_onepassword_auth = has_onepassword_auth
_get_onepassword_session_env = get_onepassword_session_env


def _check_onepassword_auth() -> bool:
    if _has_onepassword_auth():
        return True
    print(get_message("onboarding", "missing_onepassword_auth"))
    print(get_message("onboarding", "missing_onepassword_auth_hint"))
    return False


def _check_required_tool_secrets(*, pkm_source: str | None = None) -> bool:
    normalized_pkm_source = technical_context.normalize_pkm_source(pkm_source)
    skills = load_skill_definitions(DEFAULT_SKILLS_ROOT)
    required_env = sorted(
        {
            env
            for skill in skills
            for env in skill.required_env
            if env and technical_context.should_require_tool_secret(env, normalized_pkm_source)
        }
    )
    if not required_env:
        return True

    required_by_env: dict[str, list[str]] = {}
    for skill in skills:
        for env in skill.required_env:
            if not technical_context.should_require_tool_secret(env, normalized_pkm_source):
                continue
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


def _load_secret_from_1password(
    vault_name: str, item_name: str, field_label: str
) -> str | None:
    return load_secret_from_1password(
        vault_name=vault_name, item_name=item_name, field_label=field_label
    )
