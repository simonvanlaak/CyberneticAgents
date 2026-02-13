from __future__ import annotations

from typing import Iterable, Sequence, Tuple


STATUS_LABEL_PREFIX = "status:"

# Single-select status labels.
STATUS_READY = "status:ready"
STATUS_IN_PROGRESS = "status:in-progress"
STATUS_IN_REVIEW = "status:in-review"
STATUS_BLOCKED = "status:blocked"

KNOWN_STATUS_LABELS = {
    STATUS_READY,
    STATUS_IN_PROGRESS,
    STATUS_IN_REVIEW,
    STATUS_BLOCKED,
}


def apply_status_label(existing_labels: Iterable[str], new_status_label: str) -> set[str]:
    """Return a new label set with exactly one status:* label."""

    if new_status_label not in KNOWN_STATUS_LABELS:
        raise ValueError(f"Unknown status label: {new_status_label}")

    kept = {l for l in existing_labels if not l.startswith(STATUS_LABEL_PREFIX)}
    kept.add(new_status_label)
    return kept


def plan_label_changes(existing_labels: Sequence[str], new_status_label: str) -> Tuple[list[str], list[str]]:
    """Plan add/remove lists to reach the desired label set."""

    target = apply_status_label(existing_labels, new_status_label)
    existing = set(existing_labels)

    to_add = sorted(target - existing)
    to_remove = sorted(existing - target)
    return to_add, to_remove
