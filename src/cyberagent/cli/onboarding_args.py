from __future__ import annotations

import argparse


def add_onboarding_args(subparsers: argparse._SubParsersAction) -> None:
    onboarding_parser = subparsers.add_parser(
        "onboarding",
        help="Initialize the default team.",
        description="Create the default root team if none exists.",
    )
    onboarding_parser.add_argument(
        "--name",
        dest="user_name",
        type=str,
        default=None,
        help="User name for onboarding discovery.",
    )
    onboarding_parser.add_argument(
        "--repo",
        dest="repo_url",
        type=str,
        default=None,
        help="Private GitHub repo URL for the Obsidian vault.",
    )
    onboarding_parser.add_argument(
        "--profile-link",
        dest="profile_links",
        action="append",
        default=[],
        help="Profile link for web research (repeatable).",
    )
    onboarding_parser.add_argument(
        "--token-env",
        dest="token_env",
        type=str,
        default="GITHUB_READONLY_TOKEN",
        help="Env var holding the GitHub read-only token.",
    )
    onboarding_parser.add_argument(
        "--token-username",
        dest="token_username",
        type=str,
        default="x-access-token",
        help="Username to pair with the token.",
    )
