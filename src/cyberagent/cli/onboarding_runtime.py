from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from src.cyberagent.cli import dashboard_launcher
from src.cyberagent.cli.message_catalog import get_message


def start_dashboard_after_onboarding(team_id: int) -> int | None:
    # Skip dashboard launch in non-interactive environments.
    if not sys.stdin.isatty() and not sys.stdout.isatty():
        return None
    dashboard_python = dashboard_launcher.resolve_dashboard_python()
    if dashboard_python is None:
        return None
    dashboard_path = Path(__file__).resolve().parents[1] / "ui" / "dashboard.py"
    cmd = [dashboard_python, "-m", "streamlit", "run", str(dashboard_path)]
    env = os.environ.copy()
    env["CYBERAGENT_ACTIVE_TEAM_ID"] = str(team_id)
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    print(get_message("onboarding", "dashboard_starting", pid=proc.pid))
    return proc.pid


def resolve_runtime_db_url(database_url: str, database_path: str) -> str:
    if not database_url.startswith("sqlite:///"):
        return database_url
    db_path = Path(database_path)
    if not db_path.is_absolute():
        db_path = (Path.cwd() / db_path).resolve()
    return f"sqlite:///{db_path}"


def pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def load_runtime_pid(runtime_pid_file: Path) -> int | None:
    if not runtime_pid_file.exists():
        return None
    try:
        return int(runtime_pid_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
