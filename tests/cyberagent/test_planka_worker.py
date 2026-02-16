"""Tests for the Planka worker loop."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from src.cyberagent.integrations.planka.adapter import PlankaCard, PlankaList
from src.cyberagent.integrations.planka.worker import (
    PlankaExecutionResult,
    PlankaWorker,
    PlankaWorkerConfig,
)


@dataclass
class _MoveCall:
    card_id: str
    list_id: str


class _FakeAdapter:
    def __init__(self, *, lists: list[PlankaList], cards: list[PlankaCard]) -> None:
        self._lists = lists
        self._cards: dict[str, PlankaCard] = {card.card_id: card for card in cards}
        self.move_calls: list[_MoveCall] = []
        self.comment_calls: list[tuple[str, str]] = []

    def list_lists(self, board_id: str) -> list[PlankaList]:
        return [lst for lst in self._lists if lst.board_id == board_id]

    def list_cards(self, board_id: str) -> list[PlankaCard]:
        return [card for card in self._cards.values() if card.board_id == board_id]

    def move_card(self, card_id: str, list_id: str) -> PlankaCard:
        card = self._cards[card_id]
        updated = PlankaCard(
            card_id=card.card_id,
            name=card.name,
            list_id=list_id,
            board_id=card.board_id,
            description=card.description,
        )
        self._cards[card_id] = updated
        self.move_calls.append(_MoveCall(card_id=card_id, list_id=list_id))
        return updated

    def add_comment(self, card_id: str, text: str) -> None:
        self.comment_calls.append((card_id, text))


def _build_lists(board_id: str = "b-1") -> list[PlankaList]:
    return [
        PlankaList(list_id="l-pending", name="pending", board_id=board_id),
        PlankaList(list_id="l-ip", name="in_progress", board_id=board_id),
        PlankaList(list_id="l-blocked", name="blocked", board_id=board_id),
        PlankaList(list_id="l-completed", name="completed", board_id=board_id),
        PlankaList(list_id="l-rejected", name="rejected", board_id=board_id),
    ]


def _build_card(card_id: str, list_id: str, board_id: str = "b-1") -> PlankaCard:
    return PlankaCard(
        card_id=card_id,
        name=f"Card {card_id}",
        list_id=list_id,
        board_id=board_id,
    )


def test_run_once_transitions_pending_cards_and_posts_structured_comment() -> None:
    adapter = _FakeAdapter(
        lists=_build_lists(),
        cards=[_build_card("c-1", "l-pending"), _build_card("c-2", "l-pending")],
    )
    worker = PlankaWorker(
        adapter=adapter,
        config=PlankaWorkerConfig(board_id="b-1", run_id="planka-run", max_cards=2),
        execute_card=lambda _: PlankaExecutionResult(
            outcome="success", summary="Implemented task"
        ),
        now=lambda: datetime(2026, 2, 16, 12, 30, tzinfo=UTC),
    )

    processed = worker.run_once()

    assert processed == 2
    assert [(c.card_id, c.list_id) for c in adapter.move_calls] == [
        ("c-1", "l-ip"),
        ("c-1", "l-completed"),
        ("c-2", "l-ip"),
        ("c-2", "l-completed"),
    ]
    assert len(adapter.comment_calls) == 2
    assert "Outcome: SUCCESS" in adapter.comment_calls[0][1]
    assert "Worker run id: planka-run" in adapter.comment_calls[0][1]


def test_run_once_maps_executor_exception_to_failed_and_rejected_list() -> None:
    adapter = _FakeAdapter(
        lists=_build_lists(),
        cards=[_build_card("c-7", "l-pending")],
    )

    def _raise(_: PlankaCard) -> PlankaExecutionResult:
        raise RuntimeError("boom")

    worker = PlankaWorker(
        adapter=adapter,
        config=PlankaWorkerConfig(board_id="b-1", run_id="run-fail"),
        execute_card=_raise,
    )

    processed = worker.run_once()

    assert processed == 1
    assert adapter.move_calls[-1] == _MoveCall(card_id="c-7", list_id="l-rejected")
    assert "Outcome: FAILED" in adapter.comment_calls[0][1]
    assert "Error: boom" in adapter.comment_calls[0][1]


def test_run_once_raises_when_required_lists_missing() -> None:
    adapter = _FakeAdapter(
        lists=[PlankaList(list_id="l-pending", name="pending", board_id="b-1")],
        cards=[_build_card("c-1", "l-pending")],
    )
    worker = PlankaWorker(adapter=adapter, config=PlankaWorkerConfig(board_id="b-1"))

    with pytest.raises(ValueError, match="Missing required Planka lists"):
        worker.run_once()


def test_run_loop_returns_zero_when_interrupted() -> None:
    adapter = _FakeAdapter(lists=_build_lists(), cards=[])

    sleeps: list[float] = []

    def _sleep(seconds: float) -> None:
        sleeps.append(seconds)
        raise KeyboardInterrupt

    worker = PlankaWorker(
        adapter=adapter,
        config=PlankaWorkerConfig(board_id="b-1", once=False, poll_seconds=7.5),
        sleep=_sleep,
    )

    assert worker.run() == 0
    assert sleeps == [7.5]
