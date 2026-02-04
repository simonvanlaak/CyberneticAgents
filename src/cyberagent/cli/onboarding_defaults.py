from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULTS_ROOT = Path("config") / "defaults"
PROCEDURES_DIR = DEFAULTS_ROOT / "procedures"
TEAMS_DIR = DEFAULTS_ROOT / "teams"


def load_procedure_defaults() -> tuple[list[dict[str, Any]], str, str]:
    procedures: list[dict[str, Any]] = []
    onboarding_name: str | None = None
    strategy_name: str | None = None

    for path in sorted(PROCEDURES_DIR.glob("*.json")):
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        file_procedures = data.get("procedures")
        if isinstance(file_procedures, list):
            procedures.extend(
                item for item in file_procedures if isinstance(item, dict)
            )
        if isinstance(data.get("onboarding_procedure_name"), str):
            onboarding_name = data["onboarding_procedure_name"]
        if isinstance(data.get("onboarding_strategy_name"), str):
            strategy_name = data["onboarding_strategy_name"]

    if onboarding_name is None and procedures:
        first = procedures[0].get("name")
        if isinstance(first, str):
            onboarding_name = first
    if onboarding_name is None:
        onboarding_name = "First Run Discovery"
    if strategy_name is None:
        strategy_name = "Onboarding SOP"
    return procedures, onboarding_name, strategy_name


def load_root_team_defaults() -> dict[str, Any]:
    path = TEAMS_DIR / "root_team.json"
    data = _read_json(path)
    return data if isinstance(data, dict) else {}


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
