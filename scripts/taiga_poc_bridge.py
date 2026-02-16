"""One-shot Taiga adapter bridge for MVP validation (#114)."""

from __future__ import annotations

import os

from src.cyberagent.integrations.taiga.adapter import TaigaAdapter


def main() -> int:
    """Pull one assigned Taiga task, then write result + status transition."""
    adapter = TaigaAdapter.from_env()

    project_slug = os.getenv("TAIGA_PROJECT_SLUG", "cyberneticagents").strip()
    assignee = os.getenv("TAIGA_ASSIGNEE", "taiga-bot").strip()
    source_status = os.getenv("TAIGA_SOURCE_STATUS", "pending").strip()
    target_status = os.getenv("TAIGA_TARGET_STATUS", "completed").strip()
    result_comment = os.getenv(
        "TAIGA_RESULT_COMMENT",
        "Automated result: completed by CyberneticAgents Taiga PoC adapter.",
    ).strip()

    task = adapter.process_first_assigned_task(
        project_slug=project_slug,
        assignee=assignee,
        source_status_slug=source_status,
        result_comment=result_comment,
        target_status_name=target_status,
    )

    if task is None:
        print("No matching Taiga task found for the configured assignment/status.")
        return 0

    display_ref = task.ref if task.ref is not None else task.task_id
    print(
        f"Processed Taiga task #{display_ref} (id={task.task_id}) "
        f"and moved it to status '{target_status}'."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
