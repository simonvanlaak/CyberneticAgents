#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# Allow this script to be executed from any working directory.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.cyberagent.tools.github_issue_queue import (
    KNOWN_STATUS_LABELS,
    STATUS_BLOCKED,
    STATUS_IN_PROGRESS,
    STATUS_IN_REVIEW,
    STATUS_READY,
    plan_label_changes,
)


def _sh(args: list[str]) -> str:
    return subprocess.check_output(args, text=True)


def _gh_json(args: list[str]) -> Any:
    return json.loads(_sh(args))


def cmd_ensure_labels(args: argparse.Namespace) -> int:
    existing = _gh_json(["gh", "label", "list", "--repo", args.repo, "--json", "name"])
    names = {row["name"] for row in existing}

    # Use deterministic colors (arbitrary but stable).
    desired = {
        STATUS_READY: "0e8a16",  # green
        STATUS_IN_PROGRESS: "fbca04",  # yellow
        STATUS_IN_REVIEW: "1d76db",  # blue
        STATUS_BLOCKED: "d93f0b",  # red/orange
    }

    for name, color in desired.items():
        if name in names:
            continue
        subprocess.check_call(
            [
                "gh",
                "label",
                "create",
                name,
                "--repo",
                args.repo,
                "--color",
                color,
                "--description",
                "automation status label",
            ]
        )

    return 0


def _pick_next_issue(*, repo: str) -> dict[str, Any] | None:
    # Prefer oldest in-progress, else oldest ready.
    for status in (STATUS_IN_PROGRESS, STATUS_READY):
        out = _gh_json(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                repo,
                "--search",
                f'is:issue is:open label:"{status}" sort:created-asc',
                "--limit",
                "1",
                "--json",
                "number,title",
            ]
        )
        if out:
            issue = out[0]
            issue["picked_from_status"] = status
            return issue
    return None


def cmd_pick_next(args: argparse.Namespace) -> int:
    issue = _pick_next_issue(repo=args.repo)
    if not issue:
        return 1
    sys.stdout.write(json.dumps(issue) + "\n")
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    data = _gh_json(
        [
            "gh",
            "issue",
            "view",
            str(args.issue),
            "--repo",
            args.repo,
            "--json",
            "labels",
        ]
    )
    existing_labels = [l["name"] for l in (data.get("labels") or [])]

    if args.status not in KNOWN_STATUS_LABELS:
        raise SystemExit(f"Unknown --status: {args.status}")

    to_add, to_remove = plan_label_changes(existing_labels, args.status)

    edit_cmd = ["gh", "issue", "edit", str(args.issue), "--repo", args.repo]
    for l in to_add:
        edit_cmd += ["--add-label", l]
    for l in to_remove:
        edit_cmd += ["--remove-label", l]

    if len(edit_cmd) == 6:
        # No changes required.
        return 0

    subprocess.check_call(edit_cmd)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Issue-label-based queue utilities")
    p.add_argument("--repo", required=True)

    sub = p.add_subparsers(dest="cmd", required=True)

    ensure = sub.add_parser("ensure-labels")
    ensure.set_defaults(fn=cmd_ensure_labels)

    pick = sub.add_parser("pick-next")
    pick.set_defaults(fn=cmd_pick_next)

    setst = sub.add_parser("set-status")
    setst.add_argument("--issue", type=int, required=True)
    setst.add_argument("--status", required=True)
    setst.set_defaults(fn=cmd_set_status)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
