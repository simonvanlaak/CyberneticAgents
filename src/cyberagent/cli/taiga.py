"""CLI handlers for Taiga integration commands."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from src.cyberagent.integrations.taiga.adapter import TaigaAdapter
from src.cyberagent.integrations.taiga.worker import TaigaWorker, TaigaWorkerConfig


def handle_taiga_worker_command(args: argparse.Namespace) -> int:
    """Run the Taiga worker loop from CLI args + optional JSON config."""
    try:
        config_payload = _load_worker_config_payload(args.config)
        config = _resolve_worker_config(args, config_payload)
        adapter = TaigaAdapter.from_env()
        worker = TaigaWorker(adapter=adapter, config=config)
        return worker.run()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Taiga worker configuration error: {exc}", file=sys.stderr)
        return 2


def _load_worker_config_payload(config_path: str | None) -> dict[str, Any]:
    if not config_path:
        return {}

    payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Worker --config file must contain a JSON object.")
    return payload


def _resolve_worker_config(
    args: argparse.Namespace,
    payload: dict[str, Any],
) -> TaigaWorkerConfig:
    return TaigaWorkerConfig(
        project_slug=_resolve_string(
            cli_value=args.project_slug,
            file_value=payload.get("project_slug"),
            env_key="TAIGA_PROJECT_SLUG",
            default="cyberneticagents",
        ),
        assignee=_resolve_string(
            cli_value=args.assignee,
            file_value=payload.get("assignee"),
            env_key="TAIGA_ASSIGNEE",
            default="taiga-bot",
        ),
        source_status=_resolve_string(
            cli_value=args.source_status,
            file_value=payload.get("source_status"),
            env_key="TAIGA_SOURCE_STATUS",
            default="pending",
        ),
        in_progress_status=_resolve_string(
            cli_value=args.in_progress_status,
            file_value=payload.get("in_progress_status"),
            env_key="TAIGA_IN_PROGRESS_STATUS",
            default="in_progress",
        ),
        success_status=_resolve_string(
            cli_value=args.success_status,
            file_value=payload.get("success_status"),
            env_key="TAIGA_SUCCESS_STATUS",
            default="completed",
        ),
        failure_status=_resolve_string(
            cli_value=args.failure_status,
            file_value=payload.get("failure_status"),
            env_key="TAIGA_FAILURE_STATUS",
            default="blocked",
        ),
        blocked_status=_resolve_string(
            cli_value=args.blocked_status,
            file_value=payload.get("blocked_status"),
            env_key="TAIGA_BLOCKED_STATUS",
            default="blocked",
        ),
        once=_resolve_bool(
            cli_value=args.once,
            file_value=payload.get("once"),
            default=False,
        ),
        poll_seconds=_resolve_float(
            cli_value=args.poll_seconds,
            file_value=payload.get("poll_seconds"),
            env_key="TAIGA_POLL_SECONDS",
            default=30.0,
        ),
        max_tasks=_resolve_int(
            cli_value=args.max_tasks,
            file_value=payload.get("max_tasks"),
            env_key="TAIGA_MAX_TASKS",
            default=1,
        ),
        run_id=_resolve_run_id(
            cli_value=args.run_id,
            file_value=payload.get("run_id"),
            env_key="TAIGA_RUN_ID",
        ),
    )


def _resolve_string(
    *,
    cli_value: str | None,
    file_value: object,
    env_key: str,
    default: str,
) -> str:
    if cli_value is not None:
        return cli_value
    if isinstance(file_value, str) and file_value.strip():
        return file_value.strip()
    env_value = os.getenv(env_key, "").strip()
    if env_value:
        return env_value
    return default


def _resolve_bool(*, cli_value: bool | None, file_value: object, default: bool) -> bool:
    if cli_value is not None:
        return cli_value
    if isinstance(file_value, bool):
        return file_value
    return default


def _resolve_int(
    *,
    cli_value: int | None,
    file_value: object,
    env_key: str,
    default: int,
) -> int:
    if cli_value is not None:
        return cli_value
    if isinstance(file_value, int) and not isinstance(file_value, bool):
        return file_value
    env_raw = os.getenv(env_key, "").strip()
    if env_raw:
        return int(env_raw)
    return default


def _resolve_float(
    *,
    cli_value: float | None,
    file_value: object,
    env_key: str,
    default: float,
) -> float:
    if cli_value is not None:
        return cli_value
    if isinstance(file_value, (int, float)) and not isinstance(file_value, bool):
        return float(file_value)
    env_raw = os.getenv(env_key, "").strip()
    if env_raw:
        return float(env_raw)
    return default


def _resolve_run_id(*, cli_value: str | None, file_value: object, env_key: str) -> str:
    if cli_value and cli_value.strip():
        return cli_value.strip()
    if isinstance(file_value, str) and file_value.strip():
        return file_value.strip()
    env_value = os.getenv(env_key, "").strip()
    if env_value:
        return env_value
    return uuid.uuid4().hex
