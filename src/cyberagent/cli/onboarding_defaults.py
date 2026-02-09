from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULTS_ROOT = Path(__file__).resolve().parents[3] / "config" / "defaults"
PROCEDURES_DIR = DEFAULTS_ROOT / "procedures"
TEAMS_DIR = DEFAULTS_ROOT / "teams"


def load_procedure_defaults() -> list[dict[str, Any]]:
    procedures: list[dict[str, Any]] = []

    for path in sorted(PROCEDURES_DIR.glob("*.json")):
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        procedure = data.get("procedure")
        if isinstance(procedure, dict):
            procedures.append(procedure)
            continue
        file_procedures = data.get("procedures")
        if isinstance(file_procedures, list):
            procedures.extend(
                item for item in file_procedures if isinstance(item, dict)
            )
    return procedures


def load_root_team_defaults() -> dict[str, Any]:
    path = TEAMS_DIR / "root_team.json"
    data = _read_json(path)
    return data if isinstance(data, dict) else {}


def get_default_team_name(team_defaults: dict[str, Any]) -> str:
    team_block = team_defaults.get("team")
    if isinstance(team_block, dict):
        name = team_block.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return "root"


def get_default_purpose_name(team_defaults: dict[str, Any]) -> str:
    purpose = team_defaults.get("purpose")
    if isinstance(purpose, dict):
        name = purpose.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return "Onboarding SOP"


def get_default_strategy_name(team_defaults: dict[str, Any]) -> str:
    strategy = team_defaults.get("strategy")
    if isinstance(strategy, dict):
        name = strategy.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return "Onboarding SOP"


def get_auto_execute_procedure(
    team_defaults: dict[str, Any], procedures: list[dict[str, Any]]
) -> str | None:
    value = team_defaults.get("auto_execute_procedure")
    if isinstance(value, str) and value.strip():
        return value.strip()
    listed = team_defaults.get("procedures")
    if isinstance(listed, list) and listed:
        first = listed[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    if procedures:
        first_name = procedures[0].get("name")
        if isinstance(first_name, str) and first_name.strip():
            return first_name.strip()
    return None


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
