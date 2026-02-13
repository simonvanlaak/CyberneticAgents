from __future__ import annotations

import json
from typing import Any

from src.cyberagent.services import policies as policy_service
from src.cyberagent.ui.kanban_data import TaskCard, load_task_detail


def render_task_detail(task_id: int) -> str | None:
    """Return a formatted task detail view, or ``None`` when task is missing."""
    task = load_task_detail(task_id)
    if task is None:
        return None
    return _format_task_detail(task)


def _format_task_detail(task: TaskCard) -> str:
    lines = [
        f"Task #{task.id}: {task.name}",
        f"- Status: `{task.status}`",
        f"- Assignee: `{task.assignee or '-'}`",
        f"- Team: `{task.team_name}` (`{task.team_id}`)",
        f"- Purpose: `{task.purpose_name or '-'}` (`{task.purpose_id or '-'}`)",
        f"- Strategy: `{task.strategy_name or '-'}` (`{task.strategy_id or '-'}`)",
        f"- Initiative: `{task.initiative_name or '-'}` (`{task.initiative_id or '-'}`)",
        "",
        "Task Content",
        task.content or "-",
        "",
        "Status Reasoning",
        task.reasoning or "-",
        "",
        "Task Result",
        task.result or "-",
        "",
        "Execution Log",
        task.execution_log or "-",
        "",
        "Lineage",
        f"- Follow-up Task ID: `{task.follow_up_task_id or '-'}`",
        f"- Replaces Task ID: `{task.replaces_task_id or '-'}`",
        "",
        "Case Judgement",
    ]
    lines.extend(_format_case_judgement(task.case_judgement))
    return "\n".join(lines)


def _format_case_judgement(raw_case_judgement: str | None) -> list[str]:
    if not raw_case_judgement:
        return ["- No case judgement recorded."]
    try:
        parsed = json.loads(raw_case_judgement)
    except json.JSONDecodeError:
        return [raw_case_judgement]
    if not isinstance(parsed, list):
        return [raw_case_judgement]
    if len(parsed) == 0:
        return ["- No case judgement recorded."]

    lines: list[str] = []
    for idx, case in enumerate(parsed, 1):
        if not isinstance(case, dict):
            lines.append(f"- Case {idx}: {case}")
            continue
        lines.extend(_format_case_row(idx, case))
    return lines


def _format_case_row(case_index: int, case: dict[str, Any]) -> list[str]:
    judgement = str(case.get("judgement", "-"))
    reasoning = str(case.get("reasoning", "-"))
    policy_id_raw = case.get("policy_id")
    policy_id_text = "-"
    policy_name = "-"
    policy_content = "-"
    if isinstance(policy_id_raw, int):
        policy_id_text = str(policy_id_raw)
        policy = policy_service.get_policy_by_id(policy_id_raw)
        if policy is not None:
            policy_name = str(getattr(policy, "name", "-"))
            policy_content = str(getattr(policy, "content", "-"))

    return [
        (
            f"- Case {case_index}: judgement={judgement}; "
            f"policy_id={policy_id_text}; policy_name={policy_name}"
        ),
        f"  reasoning: {reasoning}",
        f"  policy_content: {policy_content}",
    ]
