from __future__ import annotations

import getpass
import json
import shutil
import subprocess
import time

from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.onboarding_secrets import has_onepassword_auth


def format_op_signin_hint() -> list[str]:
    if not shutil.which("op"):
        return [
            get_message("onboarding", "op_install_hint"),
            get_message("onboarding", "op_docs_cli"),
        ]
    return [
        get_message("onboarding", "op_service_account_hint"),
        get_message("onboarding", "op_service_docs"),
    ]


def prompt_yes_no(question: str) -> bool:
    response = input(f"{question} [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def prompt_store_secret_in_1password(
    *,
    env_name: str,
    description: str,
    doc_hint: str | None,
    vault_name: str,
) -> bool:
    if not shutil.which("op"):
        print(get_message("onboarding", "op_install_store"))
        return False
    if not has_onepassword_auth():
        for line in format_op_signin_hint():
            print(line)
        return False
    if not check_onepassword_write_access(vault_name):
        print(
            get_message(
                "onboarding",
                "onepassword_write_access_missing",
                vault_name=vault_name,
            )
        )
        print(get_message("onboarding", "onepassword_write_access_hint"))
        return False
    if not prompt_yes_no(
        get_message("onboarding", "paste_secret_prompt", description=description)
    ):
        return False
    secret_value = getpass.getpass(
        get_message("onboarding", "paste_secret_input", env_name=env_name)
    ).strip()
    if not secret_value:
        print(get_message("onboarding", "no_value_provided", env_name=env_name))
        return False
    if not ensure_onepassword_vault(vault_name):
        return False
    if not create_onepassword_item(vault_name, env_name, secret_value):
        print(get_message("onboarding", "failed_store_secret", env_name=env_name))
        if doc_hint:
            print(get_message("onboarding", "see_doc_details", doc_hint=doc_hint))
        return False
    print(get_message("onboarding", "stored_secret", env_name=env_name))
    return True


def ensure_onepassword_vault(vault_name: str) -> bool:
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
    print(
        get_message(
            "onboarding",
            "failed_create_vault",
            vault_name=vault_name,
        )
    )
    if result.stderr:
        print(
            get_message(
                "onboarding",
                "op_error_stderr",
                stderr=result.stderr.strip(),
            )
        )
    return False


def create_onepassword_item(vault_name: str, title: str, secret: str) -> bool:
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
        print(
            get_message(
                "onboarding",
                "op_error_stderr",
                stderr=result.stderr.strip(),
            )
        )
    return False


def check_onepassword_write_access(vault_name: str) -> bool:
    if not ensure_onepassword_vault(vault_name):
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
