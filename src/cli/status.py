import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from typing import Iterable, Optional

from src.init_db import init_db

TERMINAL_STATUSES = {"completed", "approved", "rejected"}


@dataclass(frozen=True)
class TaskView:
    id: int
    status: Optional[str]
    assignee: Optional[str]
    name: str
    content: str


@dataclass(frozen=True)
class InitiativeView:
    id: int
    status: Optional[str]
    name: str
    description: str
    tasks: list[TaskView]


@dataclass(frozen=True)
class StrategyView:
    id: int
    status: Optional[str]
    name: str
    description: str
    initiatives: list[InitiativeView]


@dataclass(frozen=True)
class PurposeView:
    id: int
    name: str
    content: str
    strategies: list[StrategyView]


@dataclass(frozen=True)
class TeamView:
    id: int
    name: str
    purposes: list[PurposeView]


def _is_active(status: Optional[str], active_only: bool) -> bool:
    if not active_only:
        return True
    if status is None:
        return True
    return str(status) not in TERMINAL_STATUSES


def _connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect("data/CyberneticAgents.db")
    conn.row_factory = sqlite3.Row
    return conn


def collect_status(team_id: Optional[int], active_only: bool) -> list[TeamView]:
    conn = _connect_db()
    try:
        cursor = conn.cursor()
        if team_id is None:
            cursor.execute("SELECT id, name FROM teams ORDER BY id")
        else:
            cursor.execute(
                "SELECT id, name FROM teams WHERE id = ? ORDER BY id",
                (team_id,),
            )
        teams = cursor.fetchall()
        result: list[TeamView] = []
        for team in teams:
            cursor.execute(
                "SELECT id, name, content FROM purposes WHERE team_id = ? "
                "ORDER BY id",
                (team["id"],),
            )
            purposes = cursor.fetchall()
            purpose_views: list[PurposeView] = []
            for purpose in purposes:
                cursor.execute(
                    "SELECT id, status, name, description FROM strategies "
                    "WHERE team_id = ? AND purpose_id = ? ORDER BY id",
                    (team["id"], purpose["id"]),
                )
                strategies = cursor.fetchall()
                strategy_views: list[StrategyView] = []
                for strategy in strategies:
                    status = strategy["status"]
                    if not _is_active(status, active_only):
                        continue
                    cursor.execute(
                        "SELECT id, status, name, description FROM initiatives "
                        "WHERE team_id = ? AND strategy_id = ? ORDER BY id",
                        (team["id"], strategy["id"]),
                    )
                    initiatives = cursor.fetchall()
                    initiative_views: list[InitiativeView] = []
                    for initiative in initiatives:
                        initiative_status = initiative["status"]
                        if not _is_active(initiative_status, active_only):
                            continue
                        cursor.execute(
                            "SELECT id, status, assignee, name, content FROM tasks "
                            "WHERE team_id = ? AND initiative_id = ? ORDER BY id",
                            (team["id"], initiative["id"]),
                        )
                        tasks = cursor.fetchall()
                        task_views = [
                            TaskView(
                                id=task["id"],
                                status=task["status"],
                                assignee=task["assignee"],
                                name=task["name"],
                                content=task["content"],
                            )
                            for task in tasks
                            if _is_active(task["status"], active_only)
                        ]
                        initiative_views.append(
                            InitiativeView(
                                id=initiative["id"],
                                status=initiative_status,
                                name=initiative["name"],
                                description=initiative["description"],
                                tasks=task_views,
                            )
                        )
                    strategy_views.append(
                        StrategyView(
                            id=strategy["id"],
                            status=status,
                            name=strategy["name"],
                            description=strategy["description"],
                            initiatives=initiative_views,
                        )
                    )
                purpose_views.append(
                    PurposeView(
                        id=purpose["id"],
                        name=purpose["name"],
                        content=purpose["content"],
                        strategies=strategy_views,
                    )
                )
            result.append(
                TeamView(
                    id=team["id"],
                    name=team["name"],
                    purposes=purpose_views,
                )
            )
        return result
    finally:
        conn.close()


def _format_status(status: Optional[str]) -> str:
    return str(status) if status is not None else "unknown"


def _append_lines(lines: list[str], extra_lines: Iterable[str]) -> None:
    lines.extend(extra_lines)


def render_status(teams: list[TeamView]) -> str:
    if not teams:
        return "No data found."
    lines: list[str] = []
    for team in teams:
        lines.append(f"Team {team.id}: {team.name}")
        if not team.purposes:
            lines.append("  No purposes found.")
            continue
        for purpose in team.purposes:
            lines.append(f"  Purpose {purpose.id}: {purpose.name}")
            lines.append(f"    Content: {purpose.content}")
            if not purpose.strategies:
                lines.append("    No strategies found.")
                continue
            for strategy in purpose.strategies:
                lines.append(
                    f"    Strategy {strategy.id} "
                    f"[{_format_status(strategy.status)}]: {strategy.name}"
                )
                lines.append(f"      Description: {strategy.description}")
                if not strategy.initiatives:
                    lines.append("      No initiatives found.")
                    continue
                for initiative in strategy.initiatives:
                    lines.append(
                        f"      Initiative {initiative.id} "
                        f"[{_format_status(initiative.status)}]: {initiative.name}"
                    )
                    lines.append(f"        Description: {initiative.description}")
                    if not initiative.tasks:
                        lines.append("        No tasks found.")
                        continue
                    task_lines = [
                        (
                            f"        Task {task.id} "
                            f"[{_format_status(task.status)}] "
                            f"(assignee: {task.assignee or '-'}) - {task.name}"
                        )
                        for task in initiative.tasks
                    ]
                    _append_lines(lines, task_lines)
    return "\n".join(lines)


def render_status_json(teams: list[TeamView]) -> str:
    return json.dumps({"teams": [asdict(team) for team in teams]}, indent=2)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py status",
        description="Show purposes, strategies, initiatives, and tasks.",
    )
    parser.add_argument("--team", type=int, default=None)
    parser.add_argument("--active-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    init_db()
    status = collect_status(team_id=args.team, active_only=args.active_only)
    if args.json:
        output = render_status_json(status)
    else:
        output = render_status(status)
    print(output)
    return 0
