from __future__ import annotations

from pathlib import Path

from src.cyberagent.tools.github_outbox import GitHubOutbox


def test_outbox_enqueue_dedupe_and_counts(tmp_path: Path) -> None:
    outbox = GitHubOutbox(tmp_path / "outbox.db")

    inserted1 = outbox.enqueue(kind="project_status_update", payload={"a": 1}, dedupe_key="k1")
    inserted2 = outbox.enqueue(kind="project_status_update", payload={"a": 2}, dedupe_key="k1")

    assert inserted1 is True
    assert inserted2 is False

    pending = outbox.list_pending(limit=10)
    assert len(pending) == 1
    assert pending[0].payload == {"a": 1}

    counts = outbox.counts()
    assert counts.get("pending") == 1

    outbox.mark_sent([pending[0].id])
    counts2 = outbox.counts()
    assert counts2.get("sent") == 1
