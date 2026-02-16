"""Tests for the one-shot Taiga PoC bridge script."""

from __future__ import annotations

from src.cyberagent.integrations.taiga.adapter import TaigaTask
from scripts.taiga_poc_bridge import main


class _FakeAdapter:
    def __init__(self, task: TaigaTask | None) -> None:
        self.task = task
        self.calls: list[dict[str, str]] = []

    def process_first_assigned_task(
        self,
        *,
        project_slug: str,
        assignee: str,
        source_status_slug: str,
        result_comment: str,
        target_status_name: str,
    ) -> TaigaTask | None:
        self.calls.append(
            {
                "project_slug": project_slug,
                "assignee": assignee,
                "source_status_slug": source_status_slug,
                "result_comment": result_comment,
                "target_status_name": target_status_name,
            }
        )
        return self.task


def test_main_returns_zero_when_no_matching_task(monkeypatch, capsys) -> None:
    fake_adapter = _FakeAdapter(task=None)
    monkeypatch.setattr(
        "scripts.taiga_poc_bridge.TaigaAdapter.from_env",
        lambda: fake_adapter,
    )

    exit_code = main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No matching Taiga task" in output


def test_main_processes_first_task_and_prints_summary(monkeypatch, capsys) -> None:
    fake_adapter = _FakeAdapter(
        task=TaigaTask(
            task_id=77,
            ref=12,
            subject="Verify adapter PoC",
            status_id=3,
            project_id=44,
            version=8,
        )
    )
    monkeypatch.setattr(
        "scripts.taiga_poc_bridge.TaigaAdapter.from_env",
        lambda: fake_adapter,
    )

    exit_code = main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Processed Taiga task #12" in output
    assert fake_adapter.calls[0]["project_slug"] == "cyberneticagents"
    assert fake_adapter.calls[0]["target_status_name"] == "completed"
