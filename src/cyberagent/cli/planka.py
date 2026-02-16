"""CLI handlers for Planka integration commands."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from src.cyberagent.integrations.planka.adapter import PlankaAdapter
from src.cyberagent.integrations.planka.worker import PlankaWorker, PlankaWorkerConfig


def handle_planka_worker_command(args: argparse.Namespace) -> int:
    """Run the Planka worker loop from CLI args + optional JSON config."""
    try:
        config_payload = _load_worker_config_payload(args.config)
        config = _resolve_worker_config(args, config_payload)
        adapter = PlankaAdapter.from_env()
        worker = PlankaWorker(adapter=adapter, config=config)
        return worker.run()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Planka worker configuration error: {exc}", file=sys.stderr)
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
) -> PlankaWorkerConfig:
    return PlankaWorkerConfig(
        board_id=_resolve_required_string(
            cli_value=args.board_id,
            file_value=payload.get("board_id"),
            env_key="PLANKA_BOARD_ID",
        ),
        source_list=_resolve_string(
            cli_value=args.source_list,
            file_value=payload.get("source_list"),
            env_key="PLANKA_SOURCE_LIST",
            default="pending",
        ),
        in_progress_list=_resolve_string(
            cli_value=args.in_progress_list,
            file_value=payload.get("in_progress_list"),
            env_key="PLANKA_IN_PROGRESS_LIST",
            default="in_progress",
        ),
        success_list=_resolve_string(
            cli_value=args.success_list,
            file_value=payload.get("success_list"),
            env_key="PLANKA_SUCCESS_LIST",
            default="completed",
        ),
        failure_list=_resolve_string(
            cli_value=args.failure_list,
            file_value=payload.get("failure_list"),
            env_key="PLANKA_FAILURE_LIST",
            default="rejected",
        ),
        blocked_list=_resolve_string(
            cli_value=args.blocked_list,
            file_value=payload.get("blocked_list"),
            env_key="PLANKA_BLOCKED_LIST",
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
            env_key="PLANKA_POLL_SECONDS",
            default=30.0,
        ),
        max_cards=_resolve_int(
            cli_value=args.max_cards,
            file_value=payload.get("max_cards"),
            env_key="PLANKA_MAX_CARDS",
            default=1,
        ),
        run_id=_resolve_run_id(
            cli_value=args.run_id,
            file_value=payload.get("run_id"),
            env_key="PLANKA_RUN_ID",
        ),
    )


def _resolve_required_string(
    *,
    cli_value: str | None,
    file_value: object,
    env_key: str,
) -> str:
    if cli_value is not None and cli_value.strip():
        return cli_value.strip()
    if isinstance(file_value, str) and file_value.strip():
        return file_value.strip()
    env_value = os.getenv(env_key, "").strip()
    if env_value:
        return env_value
    raise ValueError(f"Missing required Planka configuration: {env_key}")


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
