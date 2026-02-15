from __future__ import annotations

from typing import Iterable, Sequence, Tuple


STAGE_LABEL_PREFIX = "stage:"

STAGE_BACKLOG = "stage:backlog"  # parked/not in automation queue
STAGE_QUEUED = "stage:queued"  # automation triage queue
STAGE_NEEDS_CLARIFICATION = "stage:needs-clarification"
STAGE_READY_TO_IMPLEMENT = "stage:ready-to-implement"
STAGE_IN_PROGRESS = "stage:in-progress"
STAGE_IN_REVIEW = "stage:in-review"
STAGE_BLOCKED = "stage:blocked"

KNOWN_STAGE_LABELS = {
    STAGE_BACKLOG,
    STAGE_QUEUED,
    STAGE_NEEDS_CLARIFICATION,
    STAGE_READY_TO_IMPLEMENT,
    STAGE_IN_PROGRESS,
    STAGE_IN_REVIEW,
    STAGE_BLOCKED,
}


def apply_stage_label(existing_labels: Iterable[str], new_stage_label: str) -> set[str]:
    """Return a new label set with exactly one stage:* label."""

    if new_stage_label not in KNOWN_STAGE_LABELS:
        raise ValueError(f"Unknown stage label: {new_stage_label}")

    kept = {l for l in existing_labels if not l.startswith(STAGE_LABEL_PREFIX)}
    kept.add(new_stage_label)
    return kept


def plan_label_changes(existing_labels: Sequence[str], new_stage_label: str) -> Tuple[list[str], list[str]]:
    target = apply_stage_label(existing_labels, new_stage_label)
    existing = set(existing_labels)
    return sorted(target - existing), sorted(existing - target)
