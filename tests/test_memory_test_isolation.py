from __future__ import annotations

import os
from pathlib import Path


def test_memory_sqlite_path_uses_test_db_root() -> None:
    value = os.environ.get("MEMORY_SQLITE_PATH")
    assert value is not None

    resolved = Path(value).resolve()
    assert ".pytest_db" in resolved.parts
    assert resolved.name == "memory.db"

    production_path = Path("data/memory.db").resolve()
    assert resolved != production_path
