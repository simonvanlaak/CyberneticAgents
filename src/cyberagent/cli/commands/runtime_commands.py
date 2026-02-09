from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from src.cyberagent.cli.constants import (
    ONBOARDING_COMMAND,
    SERVE_COMMAND,
    SUGGEST_COMMAND,
    TEST_START_ENV,
)
from src.cyberagent.cli.headless import run_headless_session
from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.cli.runtime_resume import queue_in_progress_initiatives
from src.cyberagent.core.paths import get_logs_dir
from src.cyberagent.core.runtime import stop_runtime
from src.cyberagent.core.state import get_last_team_id, mark_team_active
from src.cyberagent.db.init_db import init_db

LOGS_DIR = get_logs_dir()
RUNTIME_PID_FILE = LOGS_DIR / "cyberagent.pid"


async def _handle_start(args: argparse.Namespace) -> int:
    if os.environ.get(TEST_START_ENV) == "1":
        print(get_message("cyberagent", "runtime_start_stubbed"))
        print(
            get_message("cyberagent", "next_suggest", suggest_command=SUGGEST_COMMAND)
        )
        return 0
    init_db()
    team_id = _require_existing_team()
    if team_id is None:
        return 1
    cmd = [sys.executable, "-m", "src.cyberagent.cli.cyberagent", SERVE_COMMAND]
    message = getattr(args, "message", None)
    if message:
        cmd.extend(["--message", message])
    env = os.environ.copy()
    env["CYBERAGENT_ACTIVE_TEAM_ID"] = str(team_id)
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    RUNTIME_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    queue_in_progress_initiatives(team_id)
    print(get_message("cyberagent", "runtime_starting", pid=proc.pid))
    print(get_message("cyberagent", "next_suggest", suggest_command=SUGGEST_COMMAND))
    return 0


def _require_existing_team() -> int | None:
    team_id = get_last_team_id()
    if team_id is None:
        print(
            get_message(
                "cyberagent",
                "no_teams_found",
                onboarding_command=ONBOARDING_COMMAND,
            )
        )
        return None
    return team_id


def _ensure_background_runtime() -> int | None:
    if _runtime_pid_is_running():
        return _load_runtime_pid()
    return _start_runtime_background()


def _runtime_pid_is_running() -> bool:
    pid = _load_runtime_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _load_runtime_pid() -> int | None:
    if not RUNTIME_PID_FILE.exists():
        return None
    try:
        return int(RUNTIME_PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _start_runtime_background() -> int | None:
    if os.environ.get(TEST_START_ENV) == "1":
        return None
    init_db()
    team_id = _require_existing_team()
    if team_id is None:
        return None
    cmd = [sys.executable, "-m", "src.cyberagent.cli.cyberagent", SERVE_COMMAND]
    env = os.environ.copy()
    env["CYBERAGENT_ACTIVE_TEAM_ID"] = str(team_id)
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    RUNTIME_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


async def _handle_stop(_: argparse.Namespace) -> int:
    _stop_background_runtime_process()
    await stop_runtime()
    _clear_runtime_pid_file()
    print(get_message("cyberagent", "runtime_stopped"))
    return 0


def _stop_background_runtime_process() -> None:
    pid = _load_runtime_pid()
    if pid is None:
        return
    if not _runtime_pid_is_running():
        return
    if not _pid_looks_like_runtime(pid):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        return
    if _wait_for_pid_exit(pid, timeout_seconds=3.0):
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return
    _wait_for_pid_exit(pid, timeout_seconds=1.0)


def _wait_for_pid_exit(pid: int, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not _is_pid_running(pid):
            return True
        time.sleep(0.05)
    return not _is_pid_running(pid)


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _pid_looks_like_runtime(pid: int) -> bool:
    cmdline_path = f"/proc/{pid}/cmdline"
    try:
        raw = Path(cmdline_path).read_bytes()
    except OSError:
        # If command line is unavailable, prefer terminating stale runtime PID.
        return True
    cmdline = raw.decode("utf-8", errors="ignore")
    return "src.cyberagent.cli.cyberagent" in cmdline and "serve" in cmdline


def _clear_runtime_pid_file() -> None:
    try:
        RUNTIME_PID_FILE.unlink()
    except OSError:
        return


async def _handle_restart(args: argparse.Namespace) -> int:
    await _handle_stop(args)
    return await _handle_start(args)


async def _handle_serve(args: argparse.Namespace) -> int:
    team_id = os.environ.get("CYBERAGENT_ACTIVE_TEAM_ID")
    if team_id:
        try:
            mark_team_active(int(team_id))
            print(get_message("cyberagent", "headless_starting", team_id=team_id))
        except ValueError:
            print(
                get_message("cyberagent", "invalid_team_id", team_id=team_id),
                file=sys.stderr,
            )
    await run_headless_session(initial_message=args.message)
    return 0
