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

from src.github_issue_queue import (
    KNOWN_STATUS_LABELS,
    STATUS_BLOCKED,
    STATUS_IN_PROGRESS,
    STATUS_IN_REVIEW,
    STATUS_READY,
    plan_label_changes,
)


def _sh(args: list[str], *, input_json: dict[str, Any] | None = None) -> str:
    if input_json is None:
        return subprocess.check_output(args, text=True)
    p = subprocess.run(args, input=json.dumps(input_json), text=True, check=False, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or f"command failed: {args}")
    return p.stdout


def _gh_api(path: str, *, method: str = "GET", fields: dict[str, Any] | None = None) -> Any:
    args = ["gh", "api", "--method", method, path]
    if fields:
        for k, v in fields.items():
            # Use -f for form fields (gh will encode)
            args += ["-f", f"{k}={v}"]
    return json.loads(_sh(args))


def _gh_api_json(path: str, *, method: str, body: dict[str, Any]) -> Any:
    return json.loads(_sh(["gh", "api", "--method", method, path], input_json=body))


def cmd_ensure_labels(args: argparse.Namespace) -> int:
    owner, repo_name = args.repo.split("/", 1)

    labels: list[dict[str, Any]] = _gh_api(f"repos/{owner}/{repo_name}/labels", fields={"per_page": 100})
    names = {row["name"] for row in labels}

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
        _gh_api_json(
            f"repos/{owner}/{repo_name}/labels",
            method="POST",
            body={"name": name, "color": color, "description": "automation status label"},
        )

    return 0


def _pick_next_issue(*, repo: str) -> dict[str, Any] | None:
    # Prefer oldest in-progress, else oldest ready.
    for status in (STATUS_IN_PROGRESS, STATUS_READY):
        q = f'repo:{repo} is:issue is:open label:"{status}" sort:created-asc'
        data = _gh_api("search/issues", fields={"q": q, "per_page": 1})
        items = data.get("items") or []
        if items:
            issue = {"number": items[0]["number"], "title": items[0]["title"], "picked_from_status": status}
            return issue
    return None


def cmd_pick_next(args: argparse.Namespace) -> int:
    issue = _pick_next_issue(repo=args.repo)
    if not issue:
        return 1
    sys.stdout.write(json.dumps(issue) + "\n")
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    owner, repo_name = args.repo.split("/", 1)

    issue = _gh_api(f"repos/{owner}/{repo_name}/issues/{args.issue}")
    existing_labels = [l["name"] for l in (issue.get("labels") or [])]

    if args.status not in KNOWN_STATUS_LABELS:
        raise SystemExit(f"Unknown --status: {args.status}")

    # Compute full target label list (single-select status label).
    from src.github_issue_queue import apply_status_label

    target_labels = sorted(apply_status_label(existing_labels, args.status))

    # PATCH issue labels (full list) via REST.
    _gh_api_json(
        f"repos/{owner}/{repo_name}/issues/{args.issue}",
        method="PATCH",
        body={"labels": target_labels},
    )
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
