from __future__ import annotations

import pytest

from src.github_stage_queue import apply_stage_label, plan_label_changes


def test_apply_stage_label_replaces_existing_stage_labels() -> None:
    labels = {"bug", "stage:backlog", "stage:blocked", "prio:p1"}
    assert apply_stage_label(labels, "stage:in-progress") == {
        "bug",
        "prio:p1",
        "stage:in-progress",
    }


def test_apply_stage_label_adds_stage_when_missing() -> None:
    assert apply_stage_label({"bug"}, "stage:backlog") == {"bug", "stage:backlog"}


@pytest.mark.parametrize(
    "stage",
    [
        "stage:backlog",
        "stage:needs-clarification",
        "stage:ready-to-implement",
        "stage:in-progress",
        "stage:in-review",
        "stage:blocked",
    ],
)
def test_apply_stage_label_accepts_known_stages(stage: str) -> None:
    assert apply_stage_label(set(), stage) == {stage}


def test_plan_label_changes_add_remove() -> None:
    add, remove = plan_label_changes(
        ["bug", "stage:backlog", "stage:blocked", "prio:p1"],
        "stage:in-progress",
    )
    assert add == ["stage:in-progress"]
    assert remove == ["stage:backlog", "stage:blocked"]
