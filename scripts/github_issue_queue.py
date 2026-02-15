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

from src.github_stage_queue import (
    KNOWN_STAGE_LABELS,
    STAGE_BACKLOG,
    STAGE_BLOCKED,
    STAGE_IN_PROGRESS,
    STAGE_IN_REVIEW,
    STAGE_NEEDS_CLARIFICATION,
    STAGE_QUEUED,
    STAGE_READY_TO_IMPLEMENT,
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
        STAGE_BACKLOG: "cfd3d7",
        STAGE_QUEUED: "ededed",
        STAGE_NEEDS_CLARIFICATION: "d4c5f9",
        STAGE_READY_TO_IMPLEMENT: "0e8a16",
        STAGE_IN_PROGRESS: "fbca04",
        STAGE_IN_REVIEW: "1d76db",
        STAGE_BLOCKED: "d93f0b",
    }

    for name, color in desired.items():
        if name in names:
            continue
        # Use form fields (gh api -f ...) because JSON stdin has been flaky with labels create.
        _gh_api(
            f"repos/{owner}/{repo_name}/labels",
            method="POST",
            fields={"name": name, "color": color, "description": "automation stage label"},
        )

    return 0


def _is_ready_to_implement_authorized(*, repo: str, issue_number: int, owner_login: str) -> bool:
    owner, repo_name = repo.split("/", 1)
    events = _gh_api(
        f"repos/{owner}/{repo_name}/issues/{issue_number}/events",
        fields={"per_page": 100},
    )
    from src.github_stage_events import is_stage_ready_set_by_owner

    return is_stage_ready_set_by_owner(events, owner_login=owner_login)


def _has_any_issue_with_label(*, repo: str, label: str) -> bool:
    q = f'repo:{repo} is:issue is:open label:"{label}"'
    data = _gh_api("search/issues", fields={"q": q, "per_page": 1})
    items = data.get("items") or []
    return bool(items)


def _pick_next_issue(*, repo: str, owner_login: str) -> dict[str, Any] | None:
    """Pick next unit of work.

    Priority policy (burst):
    1) stage:in-progress
    2) stage:queued  -> move to stage:needs-clarification and ask questions
    3) stage:ready-to-implement (owner-authorized) -> implementation

    Rationale:
    - Clarification is time-sensitive (human is active) and should be prioritized over
      starting new implementations.
    - Implementations can run later (e.g. overnight).
    """

    # 1) In progress
    q = f'repo:{repo} is:issue is:open label:"{STAGE_IN_PROGRESS}" sort:created-asc'
    data = _gh_api("search/issues", fields={"q": q, "per_page": 1})
    items = data.get("items") or []
    if items:
        return {
            "number": int(items[0]["number"]),
            "title": items[0]["title"],
            "picked_from_stage": STAGE_IN_PROGRESS,
        }

    # 2) Queued -> needs clarification
    q = f'repo:{repo} is:issue is:open label:"{STAGE_QUEUED}" sort:created-asc'
    data = _gh_api("search/issues", fields={"q": q, "per_page": 1})
    items = data.get("items") or []
    if items:
        return {
            "number": int(items[0]["number"]),
            "title": items[0]["title"],
            "picked_from_stage": STAGE_QUEUED,
        }

    # 3) Ready to implement (authorized)
    q = f'repo:{repo} is:issue is:open label:"{STAGE_READY_TO_IMPLEMENT}" sort:created-asc'
    data = _gh_api("search/issues", fields={"q": q, "per_page": 10})
    for it in (data.get("items") or []):
        n = int(it["number"])
        if not _is_ready_to_implement_authorized(repo=repo, issue_number=n, owner_login=owner_login):
            continue
        return {"number": n, "title": it["title"], "picked_from_stage": STAGE_READY_TO_IMPLEMENT}

    return None


def cmd_pick_next(args: argparse.Namespace) -> int:
    issue = _pick_next_issue(repo=args.repo, owner_login=args.owner_login)
    if not issue:
        return 1
    sys.stdout.write(json.dumps(issue) + "\n")
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    owner, repo_name = args.repo.split("/", 1)

    issue = _gh_api(f"repos/{owner}/{repo_name}/issues/{args.issue}")
    existing_labels = [l["name"] for l in (issue.get("labels") or [])]

    if args.status not in KNOWN_STAGE_LABELS:
        raise SystemExit(f"Unknown --status: {args.status}")

    # Compute full target label list (single-select stage label).
    from src.github_stage_queue import apply_stage_label

    target_labels = sorted(apply_stage_label(existing_labels, args.status))

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
    p.add_argument("--owner-login", default="simonvanlaak", help="Only pick ready-to-implement when set by this user")

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
