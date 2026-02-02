from __future__ import annotations

import argparse
from datetime import datetime
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import get_database_path, init_db
from src.cyberagent.db.models.team import Team
from src.cyberagent.tools.cli_executor.skill_runtime import DEFAULT_SKILLS_ROOT

LOGS_DIR = Path("logs")
TECH_ONBOARDING_STATE_FILE = Path("logs/technical_onboarding.json")
VAULT_NAME = "CyberneticAgents"


def handle_onboarding(args: argparse.Namespace, suggest_command: str) -> int:
    if not run_technical_onboarding_checks():
        print("Technical onboarding checks failed. Resolve the issues above.")
        return 1
    init_db()
    session = next(get_db())
    try:
        team = session.query(Team).order_by(Team.id).first()
        if team is None:
            team = Team(name="root", last_active_at=datetime.utcnow())
            session.add(team)
            session.commit()
            print(f"Created default team: {team.name} (id={team.id}).")
        else:
            print(f"Team already exists: {team.name} (id={team.id}).")
    finally:
        session.close()
    print(f"Next: run {suggest_command} to give the agents a task.")
    return 0


def run_technical_onboarding_checks() -> bool:
    state = _collect_technical_onboarding_state()
    cached = _load_technical_onboarding_state()
    if cached and cached.get("state") == state and cached.get("ok") is True:
        print("Technical onboarding already verified.")
        return True

    checks = [
        _check_db_writable,
        _check_logs_writable,
        _check_llm_credentials,
        _check_docker_available,
        _check_onepassword_auth,
        _check_required_tool_secrets,
        _check_skill_root_access,
    ]
    for check in checks:
        if not check():
            return False

    _warn_optional_api_keys()
    _save_technical_onboarding_state({"state": state, "ok": True})
    print("Technical onboarding checks passed.")
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
        "has_onepassword_auth": _has_onepassword_auth(),
        "skills_root_exists": DEFAULT_SKILLS_ROOT.exists(),
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
    print(f"{label} is not writable: {path}")
    print("Fix permissions and re-run onboarding.")
    return False


def _check_db_writable() -> bool:
    db_path = get_database_path()
    if db_path == ":memory:":
        return True
    db_file = Path(db_path)
    if not _check_path_writable("Database directory", db_file.parent):
        return False
    if db_file.exists() and not os.access(db_file, os.W_OK):
        print(f"Database file is not writable: {db_file}")
        print("Fix permissions and re-run onboarding.")
        return False
    return True


def _check_logs_writable() -> bool:
    return _check_path_writable("Logs directory", LOGS_DIR)


def _check_llm_credentials() -> bool:
    if not os.environ.get("GROQ_API_KEY"):
        loaded = _load_secret_from_1password(
            vault_name=VAULT_NAME,
            item_name="GROQ_API_KEY",
            field_label="credential",
        )
        if loaded:
            os.environ["GROQ_API_KEY"] = loaded
            print(f"Loaded GROQ_API_KEY from 1Password vault {VAULT_NAME}.")
            return True
        print("Missing GROQ_API_KEY.")
        print(
            "CyberneticAgents stores LLM provider keys in 1Password. Create a vault "
            f"named '{VAULT_NAME}' and add an item named GROQ_API_KEY."
        )
        print("Field name should be 'credential'.")
        return _prompt_store_secret_in_1password(
            env_name="GROQ_API_KEY",
            description="Groq API key",
            doc_hint=None,
        )
    if os.environ.get("LLM_PROVIDER", "groq").lower() == "mistral":
        if not os.environ.get("MISTRAL_API_KEY"):
            loaded = _load_secret_from_1password(
                vault_name=VAULT_NAME,
                item_name="MISTRAL_API_KEY",
                field_label="credential",
            )
            if loaded:
                os.environ["MISTRAL_API_KEY"] = loaded
                print(f"Loaded MISTRAL_API_KEY from 1Password vault {VAULT_NAME}.")
                return True
            print("Missing MISTRAL_API_KEY.")
            print(
                "CyberneticAgents stores LLM provider keys in 1Password. Create a vault "
                f"named '{VAULT_NAME}' and add an item named MISTRAL_API_KEY."
            )
            print("Field name should be 'credential'.")
            return _prompt_store_secret_in_1password(
                env_name="MISTRAL_API_KEY",
                description="Mistral API key",
                doc_hint=None,
            )
    return True


def _check_docker_available() -> bool:
    docker_path = shutil.which("docker")
    if not docker_path:
        print("Docker is required for tool execution but was not found in PATH.")
        return False
    try:
        result = subprocess.run(
            [docker_path, "info"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        print("Docker is installed but not reachable. Is the daemon running?")
        return False
    if result.returncode != 0:
        print("Docker is installed but not reachable. Is the daemon running?")
        return False
    return True


def _has_onepassword_auth() -> bool:
    if os.getenv("OP_SERVICE_ACCOUNT_TOKEN"):
        return True
    for key, value in os.environ.items():
        if key.startswith("OP_SESSION_") and value:
            return True
    return False


def _check_onepassword_auth() -> bool:
    if _has_onepassword_auth():
        return True
    print("Missing 1Password authentication.")
    for line in _format_op_signin_hint():
        print(line)
    return False


def _format_op_signin_hint() -> list[str]:
    if not shutil.which("op"):
        return [
            "Install the 1Password CLI (`op`) and re-run onboarding.",
            "Docs: https://developer.1password.com/docs/cli/",
        ]
    shorthand = _detect_op_account_shorthand()
    if shorthand:
        return [
            "Run the following in the same shell, then re-run onboarding:",
            f'eval "$(op signin --account {shorthand})"',
            "Alternatively: export OP_SERVICE_ACCOUNT_TOKEN=... (service accounts).",
        ]
    return [
        "Run the following in the same shell, then re-run onboarding:",
        'eval "$(op signin)"',
        "If you have multiple accounts: op account list, then",
        'eval "$(op signin --account <shorthand>)"',
        "Alternatively: export OP_SERVICE_ACCOUNT_TOKEN=... (service accounts).",
    ]


def _detect_op_account_shorthand() -> str | None:
    try:
        result = subprocess.run(
            ["op", "account", "list", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        accounts = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(accounts, list) or len(accounts) != 1:
        return None
    shorthand = accounts[0].get("shorthand") if isinstance(accounts[0], dict) else None
    if isinstance(shorthand, str) and shorthand:
        return shorthand
    return None


def _check_required_tool_secrets() -> bool:
    if not os.environ.get("BRAVE_API_KEY"):
        loaded = _load_secret_from_1password(
            vault_name=VAULT_NAME,
            item_name="BRAVE_API_KEY",
            field_label="credential",
        )
        if loaded:
            os.environ["BRAVE_API_KEY"] = loaded
            print(f"Loaded BRAVE_API_KEY from 1Password vault {VAULT_NAME}.")
            return True
        print("Missing BRAVE_API_KEY for web-search.")
        print(
            "CyberneticAgents stores tool secrets in 1Password. Create a vault named "
            f"'{VAULT_NAME}' and add an item named BRAVE_API_KEY."
        )
        print("Field name should be 'credential'.")
        print(
            "See docs for creating a Brave API key in "
            "`src/tools/skills/web-search/SKILL.md`."
        )
        return _prompt_store_secret_in_1password(
            env_name="BRAVE_API_KEY",
            description="Brave Search API key",
            doc_hint="src/tools/skills/web-search/SKILL.md",
        )
    return True


def _check_skill_root_access() -> bool:
    if not DEFAULT_SKILLS_ROOT.exists():
        print(f"Skills root not found: {DEFAULT_SKILLS_ROOT}")
        return False
    if not os.access(DEFAULT_SKILLS_ROOT, os.R_OK):
        print(f"Skills root is not readable: {DEFAULT_SKILLS_ROOT}")
        return False
    return True


def _warn_optional_api_keys() -> None:
    optional = [
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGSMITH_API_KEY",
    ]
    missing = [key for key in optional if not os.environ.get(key)]
    if missing:
        missing_str = ", ".join(missing)
        print(f"Optional API keys not set: {missing_str}.")


def _prompt_store_secret_in_1password(
    env_name: str, description: str, doc_hint: str | None
) -> bool:
    if not shutil.which("op"):
        print("Install the 1Password CLI (`op`) to store secrets automatically.")
        return False
    if not _has_onepassword_auth():
        for line in _format_op_signin_hint():
            print(line)
        return False
    if not _check_onepassword_write_access(VAULT_NAME):
        print(
            "Your 1Password session does not have write access to the "
            f"'{VAULT_NAME}' vault."
        )
        print(
            "Ask for write access or use a service account token with write "
            "permissions, then re-run onboarding."
        )
        return False
    if not _prompt_yes_no(
        f"Would you like to paste your {description} now and store it in 1Password?"
    ):
        return False
    secret_value = getpass.getpass(f"Paste {env_name}: ").strip()
    if not secret_value:
        print(f"No value provided for {env_name}.")
        return False
    if not _ensure_onepassword_vault(VAULT_NAME):
        return False
    if not _create_onepassword_item(VAULT_NAME, env_name, secret_value):
        print(f"Failed to store {env_name} in 1Password.")
        if doc_hint:
            print(f"See {doc_hint} for details.")
        return False
    os.environ[env_name] = secret_value
    print(f"Stored {env_name} in 1Password.")
    return True


def _prompt_yes_no(question: str) -> bool:
    response = input(f"{question} [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def _ensure_onepassword_vault(vault_name: str) -> bool:
    result = subprocess.run(
        ["op", "vault", "get", vault_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    result = subprocess.run(
        ["op", "vault", "create", vault_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    print(f"Failed to create 1Password vault '{vault_name}'.")
    if result.stderr:
        print(result.stderr.strip())
    return False


def _create_onepassword_item(vault_name: str, title: str, secret: str) -> bool:
    result = subprocess.run(
        [
            "op",
            "item",
            "create",
            "--category",
            "API Credential",
            "--vault",
            vault_name,
            "--title",
            title,
            f"credential={secret}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    if result.stderr:
        print(result.stderr.strip())
    return False


def _load_secret_from_1password(
    vault_name: str, item_name: str, field_label: str
) -> str | None:
    if not shutil.which("op"):
        return None
    if not _has_onepassword_auth():
        return None
    result = subprocess.run(
        [
            "op",
            "item",
            "get",
            item_name,
            "--vault",
            vault_name,
            "--fields",
            f"label={field_label}",
            "--reveal",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, list) and payload:
        value = payload[0].get("value") if isinstance(payload[0], dict) else None
        return value if isinstance(value, str) and value else None
    if isinstance(payload, dict):
        value = payload.get("value")
        return value if isinstance(value, str) and value else None
    return None


def _check_onepassword_write_access(vault_name: str) -> bool:
    if not _ensure_onepassword_vault(vault_name):
        return False
    check_title = f"cyberagent-write-check-{int(time.time())}"
    result = subprocess.run(
        [
            "op",
            "item",
            "create",
            "--category",
            "API Credential",
            "--vault",
            vault_name,
            "--title",
            check_title,
            "credential=probe",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    item_id = None
    if result.stdout:
        try:
            payload = json.loads(result.stdout)
            item_id = payload.get("id") if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            item_id = None
    if item_id:
        subprocess.run(
            ["op", "item", "delete", item_id, "--vault", vault_name],
            capture_output=True,
            text=True,
            check=False,
        )
    return True
