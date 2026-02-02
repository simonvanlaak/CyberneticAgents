from __future__ import annotations

import argparse
from datetime import datetime
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.init_db import get_database_path, init_db
from src.cyberagent.db.models.procedure import Procedure
from src.cyberagent.db.models.system import ensure_default_systems_for_team
from src.cyberagent.db.models.system import get_system_by_type
from src.cyberagent.db.models.team import Team
from src.cyberagent.services import procedures as procedures_service
from src.cyberagent.services import teams as teams_service
from src.cyberagent.tools.cli_executor.skill_loader import (
    SkillDefinition,
    load_skill_definitions,
)
from src.cyberagent.tools.cli_executor.skill_runtime import DEFAULT_SKILLS_ROOT
from src.enums import SystemType

LOGS_DIR = Path("logs")
TECH_ONBOARDING_STATE_FILE = Path("logs/technical_onboarding.json")
VAULT_NAME = "CyberneticAgents"
NETWORK_SKILL_NAMES = {"web-fetch", "web-search", "git-readonly-sync"}
TOOL_SECRET_DOC_HINTS = {
    "BRAVE_API_KEY": "src/tools/skills/web-search/SKILL.md",
}
TELEGRAM_DOC_HINT = "docs/technical/telegram_setup.md"
DEFAULT_PROCEDURES = [
    {
        "name": "First Run Discovery",
        "description": (
            "Capture initial user context, documents, and interview insights to "
            "establish a baseline purpose and strategy."
        ),
        "risk_level": "low",
        "impact": "high",
        "rollback_plan": "Revert to prior purpose/strategy and re-interview the user.",
        "tasks": [
            {
                "name": "Collect user identity and disambiguation links",
                "description": (
                    "Gather user name and confirm public profile links to avoid "
                    "misidentification."
                ),
                "position": 1,
            },
            {
                "name": "Collect user documents and sources",
                "description": (
                    "Request access to relevant docs (Notion, Obsidian, files) and "
                    "confirm what should be analyzed."
                ),
                "position": 2,
            },
            {
                "name": "Analyze documents for needs and active work",
                "description": (
                    "Summarize current projects, goals, constraints, and pain points "
                    "from provided materials."
                ),
                "position": 3,
            },
            {
                "name": "Prepare discovery interview plan",
                "description": "Draft focused questions based on known context.",
                "position": 4,
            },
            {
                "name": "Conduct discovery interview",
                "description": "Run the interview and capture answers verbatim.",
                "position": 5,
            },
            {
                "name": "Propose initial purpose and strategy",
                "description": (
                    "Draft purpose, objectives, and KPIs based on the interview."
                ),
                "position": 6,
            },
        ],
    },
    {
        "name": "Purpose Adjustment Review",
        "description": (
            "Review recent work and knowledge to refine purpose and strategy."
        ),
        "risk_level": "low",
        "impact": "medium",
        "rollback_plan": "Restore last approved purpose and log adjustments.",
        "tasks": [
            {
                "name": "Review recent initiatives and tasks",
                "description": (
                    "Summarize completed work since the last review and key outcomes."
                ),
                "position": 1,
            },
            {
                "name": "Compare new knowledge to current purpose",
                "description": (
                    "Identify gaps or changes in user needs vs the current purpose."
                ),
                "position": 2,
            },
            {
                "name": "Identify recurring tasks for automation",
                "description": (
                    "List repeatable work that could be automated or templated."
                ),
                "position": 3,
            },
            {
                "name": "Propose purpose/strategy updates",
                "description": (
                    "Draft recommended updates and user follow-up questions."
                ),
                "position": 4,
            },
        ],
    },
    {
        "name": "Product Discovery Research Loop",
        "description": (
            "Continuously update the discovery framework using best practices."
        ),
        "risk_level": "low",
        "impact": "medium",
        "rollback_plan": "Revert to the last vetted framework and note changes.",
        "tasks": [
            {
                "name": "Research interview best practices",
                "description": (
                    "Gather current guidance on user interviews and discovery."
                ),
                "position": 1,
            },
            {
                "name": "Review internal discovery notes",
                "description": (
                    "Analyze existing research syntheses and onboarding learnings."
                ),
                "position": 2,
            },
            {
                "name": "Synthesize discovery framework updates",
                "description": (
                    "Update the interview flow/guide with actionable steps."
                ),
                "position": 3,
            },
            {
                "name": "Publish updated framework summary",
                "description": ("Record changes and share with System4 and System5."),
                "position": 4,
            },
        ],
    },
]
DEFAULT_TEAM_ENVELOPE_SKILLS = [
    "speech-to-text",
]


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
    _seed_default_team_envelope(team.id)
    _seed_default_procedures(team.id)
    print(f"Next: run {suggest_command} to give the agents a task.")
    return 0


def _seed_default_procedures(team_id: int) -> None:
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

    for template in DEFAULT_PROCEDURES:
        if template["name"] in existing_names:
            continue
        procedure = procedures_service.create_procedure_draft(
            team_id=team_id,
            name=template["name"],
            description=template["description"],
            risk_level=template["risk_level"],
            impact=template["impact"],
            rollback_plan=template["rollback_plan"],
            created_by_system_id=system4.id,
            tasks=template["tasks"],
        )
        procedures_service.approve_procedure(
            procedure_id=procedure.id, approved_by_system_id=system5.id
        )


def _seed_default_team_envelope(team_id: int) -> None:
    for skill_name in DEFAULT_TEAM_ENVELOPE_SKILLS:
        teams_service.add_allowed_skill(team_id, skill_name, actor_id="onboarding")


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
        _check_docker_socket_access,
        _check_docker_available,
        _check_cli_tools_image_available,
        _check_onepassword_auth,
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
        "has_telegram_token": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "has_telegram_webhook_secret": bool(os.environ.get("TELEGRAM_WEBHOOK_SECRET")),
        "has_telegram_webhook_url": bool(os.environ.get("TELEGRAM_WEBHOOK_URL")),
        "has_onepassword_auth": _has_onepassword_auth(),
        "has_op_session": bool(_get_onepassword_session_env()),
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
            print(f"Found GROQ_API_KEY in 1Password vault {VAULT_NAME}.")
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
                print(f"Found MISTRAL_API_KEY in 1Password vault {VAULT_NAME}.")
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


def _get_docker_socket_path() -> Path | None:
    docker_host = os.environ.get("DOCKER_HOST", "")
    if docker_host.startswith("unix://"):
        socket_path = docker_host[len("unix://") :]
        if socket_path:
            return Path(socket_path)
        return None
    if docker_host:
        return None
    return Path("/var/run/docker.sock")


def _check_docker_socket_access() -> bool:
    if not _skills_require_docker():
        return True
    if not shutil.which("docker"):
        return False
    socket_path = _get_docker_socket_path()
    if socket_path is None:
        return True
    if not socket_path.exists():
        return True
    if os.access(socket_path, os.R_OK | os.W_OK):
        return True
    print(f"Docker socket is not accessible: {socket_path}")
    print("Fix Docker socket permissions and re-run onboarding.")
    return False


def _check_docker_available() -> bool:
    docker_path = shutil.which("docker")
    if not docker_path:
        if not _skills_require_docker():
            print(
                "Docker not found, but no Docker-based skills are configured. "
                "Continuing without tool execution."
            )
            return True
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
        if not _skills_require_docker():
            print(
                "Docker is installed but not reachable. "
                "Continuing without tool execution because no Docker-based "
                "skills are configured."
            )
            return True
        print("Docker is installed but not reachable. Is the daemon running?")
        return False
    return True


def _has_onepassword_auth() -> bool:
    return bool(os.getenv("OP_SERVICE_ACCOUNT_TOKEN")) or bool(
        _get_onepassword_session_env()
    )


def _get_onepassword_session_env() -> str | None:
    for key, value in os.environ.items():
        if key.startswith("OP_SESSION_") and value:
            return value
    return None


def _check_onepassword_auth() -> bool:
    if _has_onepassword_auth():
        return True
    print("Missing 1Password authentication (service account or session).")
    print("Export OP_SERVICE_ACCOUNT_TOKEN or OP_SESSION_* and re-run onboarding.")
    return False


def _skills_require_docker() -> bool:
    skills = load_skill_definitions(DEFAULT_SKILLS_ROOT)
    return len(skills) > 0


def _check_cli_tools_image_available() -> bool:
    if not _skills_require_docker():
        return True
    docker_path = shutil.which("docker")
    if not docker_path:
        return False
    image = os.getenv(
        "CLI_TOOLS_IMAGE",
        "ghcr.io/simonvanlaak/cyberneticagents-cli-tools:latest",
    )
    try:
        result = subprocess.run(
            [docker_path, "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        print("Unable to verify the CLI tools image. Is Docker running?")
        return False
    if result.returncode == 0:
        return True
    print(
        "CLI tools image is not available. Build or pull the image, then re-run "
        "onboarding."
    )
    print(f"Expected image: {image}")
    return False


def _format_op_signin_hint() -> list[str]:
    if not shutil.which("op"):
        return [
            "Install the 1Password CLI (`op`) and re-run onboarding.",
            "Docs: https://developer.1password.com/docs/cli/",
        ]
    return [
        "Set OP_SERVICE_ACCOUNT_TOKEN for a 1Password service account, then re-run onboarding.",
        "Docs: https://developer.1password.com/docs/cli/service-accounts/",
    ]


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
        if os.environ.get(env_name):
            continue
        loaded = _load_secret_from_1password(
            vault_name=VAULT_NAME,
            item_name=env_name,
            field_label="credential",
        )
        if loaded:
            print(f"Found {env_name} in 1Password vault {VAULT_NAME}.")
            continue
        skills_list = ", ".join(sorted(required_by_env.get(env_name, [])))
        print(f"Missing {env_name} for required tools: {skills_list}.")
        print(
            "CyberneticAgents stores tool secrets in 1Password. Create a vault named "
            f"'{VAULT_NAME}' and add an item named {env_name}."
        )
        print("Field name should be 'credential'.")
        doc_hint = TOOL_SECRET_DOC_HINTS.get(env_name)
        if doc_hint:
            print(f"See docs in `{doc_hint}`.")
        if not _prompt_store_secret_in_1password(
            env_name=env_name,
            description=f"{env_name} secret",
            doc_hint=doc_hint,
        ):
            return False
    return True


def _check_skill_root_access() -> bool:
    if not DEFAULT_SKILLS_ROOT.exists():
        print(f"Skills root not found: {DEFAULT_SKILLS_ROOT}")
        return False
    if not os.access(DEFAULT_SKILLS_ROOT, os.R_OK):
        print(f"Skills root is not readable: {DEFAULT_SKILLS_ROOT}")
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
    print("Network access is required for web research tools " f"({skills_list}).")
    print("Enable outbound network access and re-run onboarding.")
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
    missing = [key for key in optional if not os.environ.get(key)]
    if missing:
        missing_str = ", ".join(missing)
        print(f"Optional API keys not set: {missing_str}.")


def _offer_optional_telegram_setup() -> None:
    if not sys.stdin.isatty():
        return
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        _offer_optional_telegram_webhook_setup()
        return
    print(
        "Telegram is not configured. You can add TELEGRAM_BOT_TOKEN now to enable the "
        "Telegram channel."
    )
    if not _prompt_store_secret_in_1password(
        env_name="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token",
        doc_hint=TELEGRAM_DOC_HINT,
    ):
        return
    _offer_optional_telegram_webhook_setup()


def _offer_optional_telegram_webhook_setup() -> None:
    if os.environ.get("TELEGRAM_WEBHOOK_SECRET"):
        return
    print(
        "Webhook mode is optional. It requires TELEGRAM_WEBHOOK_URL and a secret to "
        "validate incoming requests."
    )
    if not _prompt_yes_no("Would you like to store a Telegram webhook secret now?"):
        print(f"See setup guide in `{TELEGRAM_DOC_HINT}`.")
        return
    _prompt_store_secret_in_1password(
        env_name="TELEGRAM_WEBHOOK_SECRET",
        description="Telegram webhook secret",
        doc_hint=TELEGRAM_DOC_HINT,
    )


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
