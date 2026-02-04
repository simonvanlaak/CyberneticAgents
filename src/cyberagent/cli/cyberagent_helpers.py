from __future__ import annotations

import argparse
import getpass
from pathlib import Path
from typing import Any, Callable

from src.cyberagent.cli.message_catalog import get_message


def handle_help(
    build_parser: Callable[[], argparse.ArgumentParser], topic: str | None
) -> int:
    parser = build_parser()
    if not topic:
        parser.print_help()
        return 0
    subparser = _lookup_subparser(parser, topic)
    if subparser is None:
        print(get_message("cyberagent_helpers", "unknown_help_topic", topic=topic))
        return 1
    subparser.print_help()
    return 0


def handle_login(
    token: str | None,
    *,
    keyring_available: bool,
    keyring_module: Any,
    keyring_service: str,
) -> int:
    if not token:
        token = getpass.getpass(get_message("cyberagent_helpers", "token_prompt"))
    if keyring_available and keyring_module is not None:
        keyring_module.set_password(keyring_service, "cli", token)
        print(get_message("cyberagent_helpers", "token_stored_keyring"))
    else:
        fallback = Path.home() / ".cyberagent_token"
        fallback.write_text(token, encoding="utf-8")
        print(
            get_message(
                "cyberagent_helpers",
                "keyring_unavailable",
                path=fallback,
            )
        )
    return 0


def _lookup_subparser(
    parser: argparse.ArgumentParser, name: str
) -> argparse.ArgumentParser | None:
    subparsers_action = next(
        (
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ),
        None,
    )
    if subparsers_action is None:
        return None
    return subparsers_action.choices.get(name)
