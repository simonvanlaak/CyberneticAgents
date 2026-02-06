#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="message-routing",
        description="Manage message routing rules and dead-letter queues.",
    )
    parser.add_argument("subcommand", nargs="?", default=None)
    parser.add_argument("--action", required=True)
    parser.add_argument("--team-id", type=int)
    parser.add_argument("--rule-id", type=int)
    parser.add_argument("--name")
    parser.add_argument("--channel")
    parser.add_argument("--filters")
    parser.add_argument("--targets")
    parser.add_argument("--priority", type=int)
    parser.add_argument("--active", action="store_true")
    parser.add_argument("--inactive", action="store_true")
    parser.add_argument("--status")
    return parser


def _get_db_path() -> str:
    raw = os.environ.get("CYBERAGENT_DB_URL")
    if not raw:
        repo_root = os.environ.get("CYBERAGENT_ROOT")
        if repo_root:
            db_path = (Path(repo_root) / "data" / "CyberneticAgents.db").resolve()
            raw = f"sqlite:///{db_path}"
        else:
            raw = "sqlite:///data/CyberneticAgents.db"
    parsed = urlparse(raw)
    if parsed.scheme != "sqlite":
        raise ValueError("Only sqlite databases are supported.")
    path = parsed.path or ""
    if path in {"/:memory:", ":memory:"}:
        return ":memory:"
    if path.startswith("//"):
        normalized = os.path.normpath(path)
        if normalized.startswith("//"):
            return "/" + normalized.lstrip("/")
        return normalized
    if os.path.isabs(path):
        return path
    repo_root = os.environ.get("CYBERAGENT_ROOT")
    if repo_root:
        relative = path.lstrip("/") or "data/CyberneticAgents.db"
        return str((Path(repo_root) / relative).resolve())
    return path.lstrip("/") or "data/CyberneticAgents.db"


def _connect() -> sqlite3.Connection:
    db_path = _get_db_path()
    return sqlite3.connect(db_path)


def _json_or_default(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    return json.loads(value)


def _create_rule(args: argparse.Namespace) -> dict[str, Any]:
    if args.team_id is None or args.name is None or args.channel is None:
        raise ValueError("team_id, name, and channel are required for create_rule.")
    filters = _json_or_default(args.filters, {})
    targets = _json_or_default(args.targets, [])
    priority = int(args.priority) if args.priority is not None else 0
    active = not args.inactive
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO routing_rules (
                team_id, name, channel, filters_json, targets_json,
                priority, active, created_by_system_id, updated_by_system_id,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """,
            (
                args.team_id,
                args.name,
                args.channel,
                json.dumps(filters),
                json.dumps(targets),
                priority,
                1 if active else 0,
                now,
                now,
            ),
        )
        conn.commit()
        rule_id = cursor.lastrowid
    return {"rule_id": rule_id}


def _disable_rule(args: argparse.Namespace) -> dict[str, Any]:
    if args.rule_id is None:
        raise ValueError("rule_id is required for disable_rule.")
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE routing_rules SET active = 0, updated_at = ? WHERE id = ?",
            (now, args.rule_id),
        )
        conn.commit()
    return {"rule_id": args.rule_id, "disabled": True}


def _update_rule(args: argparse.Namespace) -> dict[str, Any]:
    if args.rule_id is None:
        raise ValueError("rule_id is required for update_rule.")
    updates: dict[str, Any] = {}
    if args.name is not None:
        updates["name"] = args.name
    if args.channel is not None:
        updates["channel"] = args.channel
    if args.filters is not None:
        updates["filters_json"] = json.dumps(_json_or_default(args.filters, {}))
    if args.targets is not None:
        updates["targets_json"] = json.dumps(_json_or_default(args.targets, []))
    if args.priority is not None:
        updates["priority"] = int(args.priority)
    if args.active:
        updates["active"] = 1
    if args.inactive:
        updates["active"] = 0

    if not updates:
        return {"rule_id": args.rule_id, "updated": False}

    updates["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{key} = ?" for key in updates.keys())
    values = list(updates.values()) + [args.rule_id]
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE routing_rules SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()
    return {"rule_id": args.rule_id, "updated": True}


def _list_rules(args: argparse.Namespace) -> dict[str, Any]:
    if args.team_id is None:
        raise ValueError("team_id is required for list_rules.")
    active_only = True
    if args.inactive:
        active_only = False
    with _connect() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute(
                """
                SELECT id, name, channel, filters_json, targets_json, priority, active
                FROM routing_rules
                WHERE team_id = ? AND active = 1
                ORDER BY priority DESC, id ASC
                """,
                (args.team_id,),
            )
        else:
            cursor.execute(
                """
                SELECT id, name, channel, filters_json, targets_json, priority, active
                FROM routing_rules
                WHERE team_id = ?
                ORDER BY priority DESC, id ASC
                """,
                (args.team_id,),
            )
        rows = cursor.fetchall()
    rules = []
    for row in rows:
        rules.append(
            {
                "id": row[0],
                "name": row[1],
                "channel": row[2],
                "filters": json.loads(row[3]) if row[3] else {},
                "targets": json.loads(row[4]) if row[4] else [],
                "priority": row[5],
                "active": bool(row[6]),
            }
        )
    return {"rules": rules}


def _list_dlq(args: argparse.Namespace) -> dict[str, Any]:
    if args.team_id is None:
        raise ValueError("team_id is required for list_dlq.")
    status = args.status
    with _connect() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute(
                """
                SELECT id, channel, payload_json, reason, status, received_at
                FROM dead_letter_messages
                WHERE team_id = ? AND status = ?
                ORDER BY id ASC
                """,
                (args.team_id, status),
            )
        else:
            cursor.execute(
                """
                SELECT id, channel, payload_json, reason, status, received_at
                FROM dead_letter_messages
                WHERE team_id = ?
                ORDER BY id ASC
                """,
                (args.team_id,),
            )
        rows = cursor.fetchall()
    items = []
    for row in rows:
        items.append(
            {
                "id": row[0],
                "channel": row[1],
                "payload": json.loads(row[2]) if row[2] else {},
                "reason": row[3],
                "status": row[4],
                "received_at": row[5],
            }
        )
    return {"dead_letters": items}


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.subcommand not in (None, "run"):
        raise SystemExit(2)

    action = args.action
    handlers = {
        "create_rule": _create_rule,
        "update_rule": _update_rule,
        "disable_rule": _disable_rule,
        "list_rules": _list_rules,
        "list_dlq": _list_dlq,
    }
    handler = handlers.get(action)
    if handler is None:
        print(json.dumps({"error": f"Unknown action: {action}"}))
        raise SystemExit(2)
    try:
        result = handler(args)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        raise SystemExit(1)
    print(json.dumps({"result": result}))


if __name__ == "__main__":
    main()
