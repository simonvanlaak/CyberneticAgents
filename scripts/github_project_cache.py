#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CACHE_PATH = Path("data/github_project_cache.json")
DEFAULT_TTL_SECONDS = 6 * 60 * 60  # 6h


@dataclass(frozen=True)
class CacheResult:
    project_id: str
    status_field_id: str
    option_ids: dict[str, str]


def _sh(args: list[str]) -> str:
    return subprocess.check_output(args, text=True)


def _load_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _save_cache(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _fetch_project_and_status_ids(*, owner: str, project_number: int) -> CacheResult:
    project_id = _sh(
        [
            "gh",
            "project",
            "view",
            str(project_number),
            "--owner",
            owner,
            "--format",
            "json",
            "--jq",
            ".id",
        ]
    ).strip()

    fields_json = _sh(
        [
            "gh",
            "project",
            "field-list",
            str(project_number),
            "--owner",
            owner,
            "--format",
            "json",
        ]
    )
    fields = json.loads(fields_json)["fields"]
    status_field = next(f for f in fields if f.get("name") == "Status")

    status_field_id = str(status_field["id"])
    options = status_field.get("options") or []
    option_ids: dict[str, str] = {str(o["name"]): str(o["id"]) for o in options}

    required = ["Backlog", "Ready", "In progress", "In review", "Done", "Blocked"]
    missing = [r for r in required if r not in option_ids]
    if missing:
        raise RuntimeError(f"Status options missing in project: {missing}")

    return CacheResult(project_id=project_id, status_field_id=status_field_id, option_ids=option_ids)


def get_cached_ids(*, owner: str, project_number: int, ttl_seconds: int) -> CacheResult:
    now = time.time()
    cache = _load_cache(CACHE_PATH)
    if cache:
        cached_at = float(cache.get("cached_at", 0))
        if now - cached_at <= ttl_seconds:
            data = cache.get("data") or {}
            return CacheResult(
                project_id=str(data["project_id"]),
                status_field_id=str(data["status_field_id"]),
                option_ids=dict(data["option_ids"]),
            )

    fresh = _fetch_project_and_status_ids(owner=owner, project_number=project_number)
    _save_cache(
        CACHE_PATH,
        {
            "cached_at": now,
            "data": {
                "project_id": fresh.project_id,
                "status_field_id": fresh.status_field_id,
                "option_ids": fresh.option_ids,
            },
        },
    )
    return fresh


def main() -> int:
    p = argparse.ArgumentParser(description="Cache GitHub Project v2 IDs to reduce GraphQL calls")
    p.add_argument("--owner", required=True)
    p.add_argument("--project-number", type=int, required=True)
    p.add_argument("--ttl-seconds", type=int, default=DEFAULT_TTL_SECONDS)
    args = p.parse_args()

    res = get_cached_ids(owner=args.owner, project_number=args.project_number, ttl_seconds=args.ttl_seconds)

    # Emit shell-friendly KEY=VALUE lines.
    print(f"PROJECT_ID={res.project_id}")
    print(f"STATUS_FIELD_ID={res.status_field_id}")
    for k, v in res.option_ids.items():
        env_key = k.upper().replace(" ", "_")
        print(f"STATUS_OPTION_{env_key}={v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
