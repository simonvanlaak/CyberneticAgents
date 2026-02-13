#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from src.cyberagent.tools.github_outbox import GitHubOutbox, default_outbox_path


def _sh(args: list[str], *, input_json: dict[str, Any] | None = None) -> str:
    if input_json is None:
        return subprocess.check_output(args, text=True)
    p = subprocess.run(args, input=json.dumps(input_json), text=True, check=False, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or f"command failed: {args}")
    return p.stdout


def _graphql_rate_limit_remaining() -> tuple[int, str]:
    out = _sh([
        "gh",
        "api",
        "graphql",
        "-f",
        "query={rateLimit{remaining resetAt}}",
    ])
    data = json.loads(out)["data"]["rateLimit"]
    return int(data["remaining"]), str(data["resetAt"])


def _batch_update_project_status(ops: list[dict[str, Any]]) -> None:
    # Each op payload should contain project_id, item_id, field_id, option_id.
    # We batch them into a single graphql mutation using aliases.
    parts: list[str] = []
    for idx, p in enumerate(ops):
        alias = f"op{idx}"
        parts.append(
            f"{alias}: updateProjectV2ItemFieldValue(input: {{projectId: \"{p['project_id']}\", itemId: \"{p['item_id']}\", fieldId: \"{p['field_id']}\", value: {{ singleSelectOptionId: \"{p['option_id']}\" }} }}) {{ clientMutationId }}"
        )
    mutation = "mutation {\n  " + "\n  ".join(parts) + "\n}"

    payload = {"query": mutation, "variables": {}}
    _sh(["gh", "api", "graphql"], input_json=payload)


def cmd_enqueue_status(args: argparse.Namespace) -> int:
    outbox = GitHubOutbox(Path(args.db) if args.db else default_outbox_path())
    payload = {
        "project_id": args.project_id,
        "item_id": args.item_id,
        "field_id": args.field_id,
        "option_id": args.option_id,
    }
    dedupe_key = f"project_status:{args.item_id}:{args.option_id}"
    inserted = outbox.enqueue(kind="project_status_update", payload=payload, dedupe_key=dedupe_key)
    if args.quiet:
        return 0
    sys.stdout.write("ENQUEUED\n" if inserted else "DEDUPED\n")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    outbox = GitHubOutbox(Path(args.db) if args.db else default_outbox_path())
    sys.stdout.write(json.dumps(outbox.counts(), indent=2) + "\n")
    return 0


def cmd_drain(args: argparse.Namespace) -> int:
    outbox = GitHubOutbox(Path(args.db) if args.db else default_outbox_path())

    remaining, reset_at = _graphql_rate_limit_remaining()
    if remaining < args.min_remaining:
        if not args.quiet:
            sys.stdout.write(f"SKIP rateLimit.remaining={remaining} < {args.min_remaining} (resetAt={reset_at})\n")
        return 0

    pending = outbox.list_pending(limit=args.max_ops)
    if not pending:
        if not args.quiet:
            sys.stdout.write("EMPTY\n")
        return 0

    # Drain only project status updates for now; leave other kinds for future expansion.
    status_ops = [op for op in pending if op.kind == "project_status_update"]

    if status_ops:
        # Batch into chunks.
        chunk_size = min(args.batch_size, 25)
        for i in range(0, len(status_ops), chunk_size):
            chunk = status_ops[i : i + chunk_size]
            try:
                _batch_update_project_status([op.payload for op in chunk])
                outbox.mark_sent([op.id for op in chunk])
            except Exception as e:  # noqa: BLE001
                # Backoff on batch failure.
                for op in chunk:
                    backoff = min(3600.0, math.pow(2.0, min(10, op.attempts)) * 5.0)
                    outbox.mark_failed(op_id=op.id, error=str(e), backoff_seconds=backoff)
                # Stop after a failed batch to avoid spamming.
                if not args.quiet:
                    sys.stdout.write(f"ERROR {e}\n")
                return 1

    if not args.quiet:
        sys.stdout.write("OK\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Rate-limit-aware GitHub outbox")
    p.add_argument("--db", default=None, help="Path to outbox sqlite db")

    sub = p.add_subparsers(dest="cmd", required=True)

    enq = sub.add_parser("enqueue-status", help="Enqueue a project item status update")
    enq.add_argument("--project-id", required=True)
    enq.add_argument("--item-id", required=True)
    enq.add_argument("--field-id", required=True)
    enq.add_argument("--option-id", required=True)
    enq.add_argument("--quiet", action="store_true")
    enq.set_defaults(fn=cmd_enqueue_status)

    st = sub.add_parser("stats", help="Show outbox counts")
    st.set_defaults(fn=cmd_stats)

    dr = sub.add_parser("drain", help="Drain queued ops (rate-limit aware)")
    dr.add_argument("--min-remaining", type=int, default=500)
    dr.add_argument("--max-ops", type=int, default=50)
    dr.add_argument("--batch-size", type=int, default=20)
    dr.add_argument("--quiet", action="store_true")
    dr.set_defaults(fn=cmd_drain)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
