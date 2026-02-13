from __future__ import annotations

import argparse
import sys

from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.onboarding_prompts import _prompt_for_missing_inputs


def validate_onboarding_inputs(args: argparse.Namespace) -> bool:
    pkm_source = getattr(args, "pkm_source", None)
    repo_url = getattr(args, "repo_url", None)
    if (
        not pkm_source
        and repo_url
        and not sys.stdin.isatty()
        and not sys.stdout.isatty()
    ):
        setattr(args, "pkm_source", "github")
    if not _prompt_for_missing_inputs(args):
        return False
    user_name = getattr(args, "user_name", None)
    pkm_source = getattr(args, "pkm_source", None)
    repo_url = getattr(args, "repo_url", None)
    if not user_name:
        print(get_message("onboarding", "onboarding_needs_name"))
        return False
    if not pkm_source:
        print(get_message("onboarding", "onboarding_needs_pkm"))
        return False
    if pkm_source == "github" and not repo_url:
        print(get_message("onboarding", "onboarding_needs_repo"))
        return False
    return True
