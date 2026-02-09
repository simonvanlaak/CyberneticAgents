from __future__ import annotations

import argparse
import sys
import termios
import tty

from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.onboarding_pkm import check_notion_token


def _prompt_for_missing_inputs(args: argparse.Namespace) -> bool:
    user_name = str(getattr(args, "user_name", "") or "").strip()
    if not user_name:
        print(get_message("onboarding", "onboarding_welcome"))
        user_name = _prompt_required_value(
            get_message("onboarding", "onboarding_prompt_user_name")
        )
        setattr(args, "user_name", user_name)

    pkm_source = str(getattr(args, "pkm_source", "") or "").strip().lower()
    if not pkm_source:
        pkm_source = _prompt_pkm_source()
        setattr(args, "pkm_source", pkm_source)

    if pkm_source == "notion":
        if not check_notion_token():
            return False

    repo_url = str(getattr(args, "repo_url", "") or "").strip()
    if pkm_source == "github" and not repo_url:
        repo_url = _prompt_required_value(
            get_message("onboarding", "onboarding_prompt_repo")
        )
        setattr(args, "repo_url", repo_url)
    elif pkm_source != "github":
        setattr(args, "repo_url", "")

    profile_links = list(getattr(args, "profile_links", []) or [])
    if not profile_links:
        try:
            raw_links = input(
                get_message("onboarding", "onboarding_prompt_profile_links")
            ).strip()
        except EOFError:
            raw_links = ""
        if raw_links:
            links = [link.strip() for link in raw_links.split(",") if link.strip()]
            if links:
                setattr(args, "profile_links", links)
    return True


def _prompt_required_value(prompt: str) -> str:
    while True:
        value = input(f"{prompt}: ").strip()
        if value:
            return value
        print(get_message("onboarding", "onboarding_missing_value"))


def _prompt_pkm_source() -> str:
    options = [
        ("notion", "Notion"),
        ("github", "GitHub Repo with .md files"),
        ("skip", "Skip"),
    ]
    prompt = get_message("onboarding", "onboarding_prompt_pkm")
    return _prompt_selection(prompt, options, default_index=1)


def _prompt_selection(
    prompt: str,
    options: list[tuple[str, str]],
    *,
    default_index: int = 0,
) -> str:
    if not _supports_tty_selection():
        return _prompt_selection_fallback(prompt, options, default_index=default_index)
    return _prompt_selection_tty(prompt, options, default_index=default_index)


def _supports_tty_selection() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _prompt_selection_fallback(
    prompt: str,
    options: list[tuple[str, str]],
    *,
    default_index: int = 0,
) -> str:
    labels = [label for _value, label in options]
    values = [value for value, _label in options]
    options_text = "\n".join(f"{idx + 1}) {label}" for idx, label in enumerate(labels))
    while True:
        response = input(f"{prompt}\n{options_text}\nSelect 1-{len(options)}: ").strip()
        if not response and 0 <= default_index < len(values):
            return values[default_index]
        if response.isdigit():
            index = int(response) - 1
            if 0 <= index < len(values):
                return values[index]
        normalized = response.lower()
        for value, label in options:
            if normalized == value or normalized == label.lower():
                return value
        print(get_message("onboarding", "onboarding_invalid_choice"))


def _prompt_selection_tty(
    prompt: str,
    options: list[tuple[str, str]],
    *,
    default_index: int = 0,
) -> str:
    index = min(max(default_index, 0), len(options) - 1)
    labels = [label for _value, label in options]
    print(prompt)

    def _render(first: bool = False) -> None:
        if not first:
            sys.stdout.write(f"\x1b[{len(labels)}A")
        for idx, label in enumerate(labels):
            prefix = ">" if idx == index else " "
            sys.stdout.write("\x1b[2K\r")
            sys.stdout.write(f"{prefix} {label}\n")
        sys.stdout.flush()

    stdin_fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(stdin_fd)
    try:
        tty.setraw(stdin_fd)
        _render(first=True)
        while True:
            key = _read_key()
            if key in {"\r", "\n"}:
                break
            if key in {"\x1b[A", "k"}:
                index = (index - 1) % len(options)
                _render()
            elif key in {"\x1b[B", "j"}:
                index = (index + 1) % len(options)
                _render()
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return options[index][0]


def _read_key() -> str:
    char = sys.stdin.read(1)
    if char == "\x1b":
        return char + sys.stdin.read(2)
    return char
