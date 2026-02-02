from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import policy_database


@pytest.fixture()
def temp_policy_db(tmp_path: Path) -> None:
    db_path = tmp_path / "policy.db"
    engine = create_engine(f"sqlite:///{db_path}")
    policy_database.engine = engine
    policy_database.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    policy_database.Base.metadata.create_all(bind=engine)


def test_create_and_get_policy_prompt(temp_policy_db: None) -> None:
    policy_database.create_policy_prompt("system-1", "policy content")

    policy = policy_database.get_policy_prompt("system-1")

    assert policy is not None
    assert cast(str, policy.system_id) == "system-1"
    assert cast(str, policy.content) == "policy content"


def test_create_policy_prompt_duplicate_raises(temp_policy_db: None) -> None:
    policy_database.create_policy_prompt("system-dup", "first")

    with pytest.raises(ValueError, match="Policy already exists"):
        policy_database.create_policy_prompt("system-dup", "second")


def test_create_policy_prompt_too_long_raises(temp_policy_db: None) -> None:
    too_long = "x" * 5001

    with pytest.raises(ValueError, match="exceeds 5000"):
        policy_database.create_policy_prompt("system-long", too_long)


def test_update_policy_prompt(temp_policy_db: None) -> None:
    policy_database.create_policy_prompt("system-update", "old")

    updated = policy_database.update_policy_prompt("system-update", "new")

    assert updated is not None
    assert cast(str, updated.content) == "new"


def test_update_policy_prompt_missing_returns_none(temp_policy_db: None) -> None:
    assert policy_database.update_policy_prompt("system-missing", "value") is None


def test_delete_policy_prompt(temp_policy_db: None) -> None:
    policy_database.create_policy_prompt("system-delete", "content")

    assert policy_database.delete_policy_prompt("system-delete") is True
    assert policy_database.get_policy_prompt("system-delete") is None


def test_delete_policy_prompt_missing_returns_false(temp_policy_db: None) -> None:
    assert policy_database.delete_policy_prompt("system-none") is False


def test_list_policy_prompts(temp_policy_db: None) -> None:
    policy_database.create_policy_prompt("system-a", "a")
    policy_database.create_policy_prompt("system-b", "b")

    policies = policy_database.list_policy_prompts()

    system_ids = {policy.system_id for policy in policies}
    assert {"system-a", "system-b"}.issubset(system_ids)
