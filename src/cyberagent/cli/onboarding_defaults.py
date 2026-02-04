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


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
