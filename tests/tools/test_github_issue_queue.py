from __future__ import annotations

import pytest

from src.github_issue_queue import apply_status_label


def test_apply_status_label_replaces_existing_status_labels() -> None:
    labels = {"bug", "status:ready", "status:blocked", "prio:p1"}
    assert apply_status_label(labels, "status:in-progress") == {
        "bug",
        "prio:p1",
        "status:in-progress",
    }


def test_apply_status_label_adds_status_when_missing() -> None:
    labels = {"bug"}
    assert apply_status_label(labels, "status:ready") == {"bug", "status:ready"}


@pytest.mark.parametrize(
    "status",
    ["status:ready", "status:in-progress", "status:in-review", "status:blocked"],
)
def test_apply_status_label_accepts_known_statuses(status: str) -> None:
    assert apply_status_label(set(), status) == {status}


def test_plan_label_changes_returns_minimal_add_remove() -> None:
    from src.github_issue_queue import plan_label_changes

    add, remove = plan_label_changes(
        ["bug", "status:ready", "status:blocked", "prio:p1"],
        "status:in-progress",
    )
    assert add == ["status:in-progress"]
    assert remove == ["status:blocked", "status:ready"]
