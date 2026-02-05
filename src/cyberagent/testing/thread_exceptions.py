"""Thread exception tracking helpers for tests."""

from __future__ import annotations

from dataclasses import dataclass
import traceback
from typing import List


@dataclass(frozen=True)
class ThreadExceptionRecord:
    thread_name: str
    exc_type: str
    exc_message: str
    traceback: str


class ThreadExceptionTracker:
    """Collect exceptions raised in background threads."""

    def __init__(self) -> None:
        self._records: List[ThreadExceptionRecord] = []

    @property
    def count(self) -> int:
        return len(self._records)

    def handle(self, args: object) -> None:
        thread = getattr(args, "thread", None)
        exc_type = getattr(args, "exc_type", None)
        exc_value = getattr(args, "exc_value", None)
        exc_traceback = getattr(args, "exc_traceback", None)
        thread_name = getattr(thread, "name", "<unknown>")
        exc_type_name = getattr(exc_type, "__name__", str(exc_type))
        exc_message = str(exc_value)
        formatted = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
        self._records.append(
            ThreadExceptionRecord(
                thread_name=thread_name,
                exc_type=exc_type_name,
                exc_message=exc_message,
                traceback=formatted,
            )
        )

    def summary(self) -> str:
        if not self._records:
            return "No background thread exceptions recorded."
        lines = ["Background thread exceptions:"]
        for record in self._records:
            lines.append(
                f"- {record.thread_name}: {record.exc_type}({record.exc_message})"
            )
        return "\n".join(lines)

    def raise_if_any(self) -> None:
        if self._records:
            raise RuntimeError(self.summary())
