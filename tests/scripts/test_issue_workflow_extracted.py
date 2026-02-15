from __future__ import annotations

from pathlib import Path


LEGACY_WORKFLOW_FILES = (
    "scripts/nightly-cyberneticagents.sh",
    "scripts/run_project_automation.sh",
    "scripts/cron_cyberneticagents_worker.sh",
    "scripts/github_issue_queue.py",
    "src/github_issue_queue.py",
    "src/github_stage_queue.py",
    "src/github_stage_events.py",
)


def test_issue_workflow_files_were_extracted_to_standalone_repo() -> None:
    """CyberneticAgents should no longer contain standalone issue-workflow code."""

    repo_root = Path(__file__).resolve().parents[2]
    for rel_path in LEGACY_WORKFLOW_FILES:
        assert not (repo_root / rel_path).exists(), f"Legacy workflow file still present: {rel_path}"
