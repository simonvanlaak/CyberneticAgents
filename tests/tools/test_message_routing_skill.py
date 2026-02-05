from __future__ import annotations

import importlib.util
import os
import sqlite3
from pathlib import Path

from src.cyberagent.db import init_db


def _load_skill_module(tmp_path: Path):
    module_path = (
        Path("src") / "tools" / "skills" / "message-routing" / "message_routing.py"
    )
    spec = importlib.util.spec_from_file_location("message_routing", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _configure_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "routing_skill.db"
    init_db.configure_database(f"sqlite:///{db_path}")
    init_db.init_db()
    os.environ["CYBERAGENT_DB_URL"] = f"sqlite:///{db_path}"
    return db_path


def test_update_rule_updates_fields(tmp_path: Path) -> None:
    module = _load_skill_module(tmp_path)
    db_path = _configure_db(tmp_path)
    args = module._build_parser().parse_args(
        [
            "--action",
            "create_rule",
            "--team-id",
            "1",
            "--name",
            "Initial",
            "--channel",
            "cli",
            "--targets",
            '[{"system_id": "System4/root"}]',
        ]
    )
    result = module._create_rule(args)
    rule_id = result["rule_id"]

    update_args = module._build_parser().parse_args(
        [
            "--action",
            "update_rule",
            "--rule-id",
            str(rule_id),
            "--name",
            "Updated",
            "--filters",
            '{"session_id": "cli-main"}',
            "--inactive",
        ]
    )
    module._update_rule(update_args)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, filters_json, active FROM routing_rules WHERE id = ?",
        (rule_id,),
    )
    row = cursor.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "Updated"
    assert "cli-main" in row[1]
    assert row[2] == 0
