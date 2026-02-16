"""Operational Planka worker loop for card claim/execute/transition flow."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import sleep as _sleep
from typing import Callable, Literal

from src.cyberagent.integrations.planka.adapter import PlankaAdapter, PlankaCard, PlankaList

PlankaOutcome = Literal["success", "failed", "blocked"]


@dataclass(frozen=True)
class PlankaExecutionResult:
    """Execution result captured for card comments + list mapping."""

    outcome: PlankaOutcome
    summary: str
    error: str | None = None


@dataclass(frozen=True)
class PlankaWorkerConfig:
    """Runtime configuration for the Planka worker loop."""

    board_id: str
    source_list: str = "pending"
    in_progress_list: str = "in_progress"
    success_list: str = "completed"
    failure_list: str = "rejected"
    blocked_list: str = "blocked"
    once: bool = False
    poll_seconds: float = 30.0
    max_cards: int = 1
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if not self.board_id.strip():
            raise ValueError("board_id must be provided.")
        if self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be greater than 0.")
        if self.max_cards <= 0:
            raise ValueError("max_cards must be greater than 0.")


class PlankaWorker:
    """Deterministic worker loop that claims and resolves Planka cards."""

    def __init__(
        self,
        *,
        adapter: PlankaAdapter,
        config: PlankaWorkerConfig,
        execute_card: Callable[[PlankaCard], PlankaExecutionResult] | None = None,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._adapter = adapter
        self._config = config
        self._execute_card = execute_card or self._default_execute_card
        self._now = now or _utc_now
        self._sleep = sleep or _sleep
        self._logger = logger or logging.getLogger(__name__)

    def run(self) -> int:
        """Run the worker in once or loop mode."""
        if self._config.once:
            processed = self.run_once()
            self._logger.info(
                "Planka worker completed one-shot run (processed=%s).", processed
            )
            return 0

        try:
            while True:
                processed = self.run_once()
                self._logger.info(
                    "Planka worker loop tick complete (processed=%s).", processed
                )
                self._sleep(self._config.poll_seconds)
        except KeyboardInterrupt:
            self._logger.info("Planka worker interrupted; stopping cleanly.")
            return 0

    def run_once(self) -> int:
        """Process up to max_cards cards from the configured source list."""
        lists_by_name = self._resolve_required_lists()

        source_list = lists_by_name[_normalize_name(self._config.source_list)]
        in_progress_list = lists_by_name[_normalize_name(self._config.in_progress_list)]

        cards = self._adapter.list_cards(self._config.board_id)
        source_cards = [card for card in cards if card.list_id == source_list.list_id]
        if not source_cards:
            return 0

        processed = 0
        for card in source_cards:
            if processed >= self._config.max_cards:
                break

            claimed = self._claim_card(card=card, target_list=in_progress_list)
            if not claimed:
                continue

            result = self._execute_with_failure_capture(card)
            self._transition_with_result(card.card_id, result, lists_by_name)
            processed += 1

        return processed

    def _resolve_required_lists(self) -> dict[str, PlankaList]:
        board_lists = self._adapter.list_lists(self._config.board_id)
        lists_by_name: dict[str, PlankaList] = {
            _normalize_name(lst.name): lst for lst in board_lists
        }

        required_names = [
            self._config.source_list,
            self._config.in_progress_list,
            self._config.success_list,
            self._config.failure_list,
            self._config.blocked_list,
        ]

        missing = [
            name
            for name in required_names
            if _normalize_name(name) not in lists_by_name
        ]
        if missing:
            rendered = ", ".join(missing)
            raise ValueError(
                "Missing required Planka lists on board "
                f"'{self._config.board_id}': {rendered}"
            )

        return lists_by_name

    def _claim_card(self, *, card: PlankaCard, target_list: PlankaList) -> bool:
        try:
            self._adapter.move_card(card.card_id, target_list.list_id)
            return True
        except Exception:  # pragma: no cover - defensive safety net
            self._logger.exception(
                "Skipped card id=%s due to claim/transition failure.",
                card.card_id,
            )
            return False

    def _execute_with_failure_capture(self, card: PlankaCard) -> PlankaExecutionResult:
        try:
            return self._execute_card(card)
        except Exception as exc:  # pragma: no cover - defensive safety net
            self._logger.exception("Card execution failed for card id=%s", card.card_id)
            return PlankaExecutionResult(
                outcome="failed",
                summary="Card execution failed before completion.",
                error=str(exc),
            )

    def _transition_with_result(
        self,
        card_id: str,
        result: PlankaExecutionResult,
        lists_by_name: dict[str, PlankaList],
    ) -> None:
        target_list_name = self._target_list_name_for_outcome(result.outcome)
        target_list = lists_by_name[_normalize_name(target_list_name)]

        comment = self._render_result_comment(result)
        self._adapter.add_comment(card_id, comment)
        self._adapter.move_card(card_id, target_list.list_id)

    def _target_list_name_for_outcome(self, outcome: PlankaOutcome) -> str:
        if outcome == "success":
            return self._config.success_list
        if outcome == "blocked":
            return self._config.blocked_list
        return self._config.failure_list

    def _render_result_comment(self, result: PlankaExecutionResult) -> str:
        timestamp = self._now().astimezone(UTC).isoformat().replace("+00:00", "Z")
        lines = [
            f"Outcome: {result.outcome.upper()}",
            f"Summary: {_single_line(result.summary, fallback='No summary provided.')}",
        ]
        if result.error:
            lines.append(f"Error: {_single_line(result.error, fallback='n/a')}")
        lines.extend(
            [
                f"Worker run id: {self._config.run_id}",
                f"Timestamp (UTC): {timestamp}",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _default_execute_card(card: PlankaCard) -> PlankaExecutionResult:
        return PlankaExecutionResult(
            outcome="success",
            summary=(
                "Automated Planka worker completed card processing with default "
                f"executor for '{card.name}'."
            ),
        )


def _single_line(value: str, *, fallback: str) -> str:
    collapsed = " ".join(value.strip().split())
    if not collapsed:
        return fallback
    return collapsed


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)
