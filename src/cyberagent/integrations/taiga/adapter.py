"""Thin Taiga task adapter used for the MVP bridge PoC."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class TaigaTask:
    """Minimal task projection needed by the MVP bridge loop."""

    task_id: int
    ref: int | None
    subject: str
    status_id: int
    project_id: int
    version: int


class TaigaAdapter:
    """Small Taiga REST adapter for polling and status/comment write-back."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_seconds: int = 20,
        session: requests.Session | Any | None = None,
    ) -> None:
        cleaned_base = base_url.strip().rstrip("/")
        if not cleaned_base:
            raise ValueError("Taiga base URL cannot be empty.")

        self._api_base_url = f"{cleaned_base}/api/v1"
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

    @classmethod
    def from_env(cls) -> "TaigaAdapter":
        """Create adapter from environment variables used by the PoC script."""
        base_url = os.getenv("TAIGA_BASE_URL", "").strip()
        token = os.getenv("TAIGA_TOKEN", "").strip()

        missing: list[str] = []
        if not base_url:
            missing.append("TAIGA_BASE_URL")
        if not token:
            missing.append("TAIGA_TOKEN")
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"Missing required Taiga configuration: {missing_text}")

        return cls(base_url=base_url, token=token)

    def list_assigned_tasks(
        self,
        *,
        project_slug: str,
        assignee: str,
        status_slug: str,
    ) -> list[TaigaTask]:
        """List project tasks assigned to an identity and status slug."""
        response = self._session.get(
            f"{self._api_base_url}/tasks",
            params={
                "project__slug": project_slug,
                "assigned_to": assignee,
                "status__slug": status_slug,
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()

        raw_payload = response.json()
        if not isinstance(raw_payload, list):
            raise ValueError("Unexpected Taiga tasks payload: expected list.")

        return [
            self._parse_task(item) for item in raw_payload if isinstance(item, dict)
        ]

    def get_task(self, task_id: int) -> TaigaTask:
        """Fetch one Taiga task by id."""
        response = self._session.get(
            f"{self._api_base_url}/tasks/{task_id}",
            params={},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected Taiga task payload: expected object.")
        return self._parse_task(payload)

    def validate_required_statuses(
        self,
        *,
        project_id: int,
        required_status_names: tuple[str, ...],
    ) -> None:
        """Ensure configured status names exist in the target Taiga project."""
        response = self._session.get(
            f"{self._api_base_url}/task-statuses",
            params={"project": project_id},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Unexpected Taiga task-statuses payload: expected list.")

        available: set[str] = set()
        for raw_status in payload:
            if not isinstance(raw_status, dict):
                continue
            name = str(raw_status.get("name", "")).strip().lower()
            slug = str(raw_status.get("slug", "")).strip().lower()
            if name:
                available.add(name)
            if slug:
                available.add(slug)

        missing = [
            name
            for name in required_status_names
            if name.strip().lower() not in available
        ]
        if missing:
            joined_missing = ", ".join(sorted(missing))
            raise ValueError(
                "Missing required Taiga task statuses for project "
                f"{project_id}: {joined_missing}"
            )

    def claim_task(self, task: TaigaTask, *, target_status_name: str) -> bool:
        """Try to claim a pending task by transitioning it to in-progress with OCC."""
        target_status_id = self._resolve_task_status_id(
            project_id=task.project_id,
            target_status_name=target_status_name,
        )

        response = self._session.patch(
            f"{self._api_base_url}/tasks/{task.task_id}",
            json={
                "version": task.version,
                "status": target_status_id,
            },
            timeout=self._timeout_seconds,
        )
        if getattr(response, "status_code", None) in {409, 412}:
            return False
        response.raise_for_status()
        return True

    def append_result_and_transition(
        self,
        *,
        task_id: int,
        result_comment: str,
        target_status_name: str,
    ) -> None:
        """Append result text and transition task status in one Taiga patch call."""
        task = self.get_task(task_id)
        target_status_id = self._resolve_task_status_id(
            project_id=task.project_id,
            target_status_name=target_status_name,
        )

        response = self._session.patch(
            f"{self._api_base_url}/tasks/{task_id}",
            json={
                "version": task.version,
                "status": target_status_id,
                "comment": result_comment,
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()

    def process_first_assigned_task(
        self,
        *,
        project_slug: str,
        assignee: str,
        source_status_slug: str,
        result_comment: str,
        target_status_name: str,
    ) -> TaigaTask | None:
        """Run one poll/write-back loop for the first matching assigned task."""
        tasks = self.list_assigned_tasks(
            project_slug=project_slug,
            assignee=assignee,
            status_slug=source_status_slug,
        )
        if not tasks:
            return None

        selected_task = tasks[0]
        self.append_result_and_transition(
            task_id=selected_task.task_id,
            result_comment=result_comment,
            target_status_name=target_status_name,
        )
        return selected_task

    def _resolve_task_status_id(
        self, *, project_id: int, target_status_name: str
    ) -> int:
        response = self._session.get(
            f"{self._api_base_url}/task-statuses",
            params={"project": project_id},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Unexpected Taiga task-statuses payload: expected list.")

        target_normalized = target_status_name.strip().lower()
        for raw_status in payload:
            if not isinstance(raw_status, dict):
                continue
            candidate_name = str(raw_status.get("name", "")).strip().lower()
            candidate_slug = str(raw_status.get("slug", "")).strip().lower()
            if target_normalized not in {candidate_name, candidate_slug}:
                continue
            return _as_int(
                raw_status.get("id"),
                field_name="task-status.id",
            )

        raise ValueError(
            f"Unable to transition Taiga task: target status '{target_status_name}' "
            f"not found in project {project_id}."
        )

    def _parse_task(self, raw_task: dict[str, object]) -> TaigaTask:
        if "subject" not in raw_task:
            raise ValueError("Invalid Taiga task payload: missing required fields.")

        task_id = _as_int(raw_task.get("id"), field_name="task.id")
        status_id = _as_int(raw_task.get("status"), field_name="task.status")
        project_id = _as_int(raw_task.get("project"), field_name="task.project")
        version = _as_int(raw_task.get("version"), field_name="task.version")
        subject = str(raw_task["subject"])

        ref_raw = raw_task.get("ref")
        ref: int | None
        if ref_raw is None:
            ref = None
        else:
            try:
                ref = _as_int(ref_raw, field_name="task.ref")
            except ValueError:
                ref = None

        return TaigaTask(
            task_id=task_id,
            ref=ref,
            subject=subject,
            status_id=status_id,
            project_id=project_id,
            version=version,
        )


def _as_int(value: object, *, field_name: str) -> int:
    """Parse integer values from Taiga JSON payloads with explicit errors."""
    if isinstance(value, bool):
        raise ValueError(
            f"Invalid Taiga payload for {field_name}: boolean values are not allowed."
        )
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            try:
                return int(stripped)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid Taiga payload for {field_name}: '{value}' is not an integer."
                ) from exc

    raise ValueError(
        f"Invalid Taiga payload for {field_name}: value is missing or non-integer."
    )
