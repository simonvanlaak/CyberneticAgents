"""Tests for the Planka adapter (issue #132)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.cyberagent.integrations.planka.adapter import (
    PlankaAdapter,
    PlankaBoard,
    PlankaCard,
    PlankaList,
)


# ---------------------------------------------------------------------------
# Minimal fakes for plankapy objects
# ---------------------------------------------------------------------------


@dataclass
class _FakeCard:
    id: str
    name: str
    listId: str
    boardId: str
    description: str = ""
    _moved_to: str | None = None
    _comments: list[str] = field(default_factory=list)

    def move(self, list_obj: Any) -> "_FakeCard":
        self.listId = list_obj.id
        self.boardId = list_obj.boardId
        self._moved_to = list_obj.id
        return self

    def add_comment(self, text: str) -> None:
        self._comments.append(text)


@dataclass
class _FakeList:
    id: str
    name: str
    boardId: str
    _cards: list[_FakeCard] = field(default_factory=list)

    @property
    def cards(self) -> list[_FakeCard]:
        return list(self._cards)

    def create_card(self, name: str, position: int = 0, description: str = "") -> _FakeCard:
        card = _FakeCard(
            id=f"card-{len(self._cards) + 1}",
            name=name,
            listId=self.id,
            boardId=self.boardId,
            description=description,
        )
        self._cards.append(card)
        return card


@dataclass
class _FakeBoard:
    id: str
    name: str
    projectId: str
    _lists: list[_FakeList] = field(default_factory=list)
    _cards: list[_FakeCard] = field(default_factory=list)

    @property
    def lists(self) -> list[_FakeList]:
        return list(self._lists)

    @property
    def cards(self) -> list[_FakeCard]:
        return list(self._cards)


@dataclass
class _FakeProject:
    id: str
    name: str
    _boards: list[_FakeBoard] = field(default_factory=list)

    @property
    def boards(self) -> list[_FakeBoard]:
        return list(self._boards)


class _FakePlanka:
    def __init__(self, projects: list[_FakeProject]) -> None:
        self._projects = projects

    @property
    def projects(self) -> list[_FakeProject]:
        return list(self._projects)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_fake_planka() -> _FakePlanka:
    card_a = _FakeCard(id="c-1", name="Card A", listId="l-1", boardId="b-1")
    card_b = _FakeCard(id="c-2", name="Card B", listId="l-2", boardId="b-1")

    list_todo = _FakeList(id="l-1", name="To Do", boardId="b-1", _cards=[card_a])
    list_done = _FakeList(id="l-2", name="Done", boardId="b-1", _cards=[card_b])

    board = _FakeBoard(
        id="b-1",
        name="Sprint Board",
        projectId="p-1",
        _lists=[list_todo, list_done],
        _cards=[card_a, card_b],
    )
    project = _FakeProject(id="p-1", name="Project Alpha", _boards=[board])
    return _FakePlanka(projects=[project])


# ---------------------------------------------------------------------------
# list_boards
# ---------------------------------------------------------------------------


def test_list_boards_returns_all_boards() -> None:
    fake_planka = _make_fake_planka()
    adapter = PlankaAdapter(planka=fake_planka)  # type: ignore[arg-type]

    boards = adapter.list_boards()

    assert len(boards) == 1
    assert isinstance(boards[0], PlankaBoard)
    assert boards[0].board_id == "b-1"
    assert boards[0].name == "Sprint Board"
    assert boards[0].project_id == "p-1"


def test_list_boards_empty_when_no_projects() -> None:
    adapter = PlankaAdapter(planka=_FakePlanka(projects=[]))  # type: ignore[arg-type]
    assert adapter.list_boards() == []


# ---------------------------------------------------------------------------
# list_lists
# ---------------------------------------------------------------------------


def test_list_lists_returns_lists_for_board() -> None:
    fake_planka = _make_fake_planka()
    adapter = PlankaAdapter(planka=fake_planka)  # type: ignore[arg-type]

    lists = adapter.list_lists("b-1")

    assert len(lists) == 2
    assert all(isinstance(lst, PlankaList) for lst in lists)
    names = {lst.name for lst in lists}
    assert names == {"To Do", "Done"}


def test_list_lists_raises_for_unknown_board() -> None:
    adapter = PlankaAdapter(planka=_make_fake_planka())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Board 'no-such' not found"):
        adapter.list_lists("no-such")


# ---------------------------------------------------------------------------
# list_cards
# ---------------------------------------------------------------------------


def test_list_cards_returns_cards_for_board() -> None:
    fake_planka = _make_fake_planka()
    adapter = PlankaAdapter(planka=fake_planka)  # type: ignore[arg-type]

    cards = adapter.list_cards("b-1")

    assert len(cards) == 2
    assert all(isinstance(c, PlankaCard) for c in cards)
    names = {c.name for c in cards}
    assert names == {"Card A", "Card B"}


def test_list_cards_raises_for_unknown_board() -> None:
    adapter = PlankaAdapter(planka=_make_fake_planka())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Board 'nope' not found"):
        adapter.list_cards("nope")


# ---------------------------------------------------------------------------
# get_card
# ---------------------------------------------------------------------------


def test_get_card_returns_matching_card() -> None:
    adapter = PlankaAdapter(planka=_make_fake_planka())  # type: ignore[arg-type]

    card = adapter.get_card("c-1")

    assert isinstance(card, PlankaCard)
    assert card.card_id == "c-1"
    assert card.name == "Card A"
    assert card.list_id == "l-1"
    assert card.board_id == "b-1"


def test_get_card_raises_for_unknown_id() -> None:
    adapter = PlankaAdapter(planka=_make_fake_planka())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Card 'x-99' not found"):
        adapter.get_card("x-99")


# ---------------------------------------------------------------------------
# create_card
# ---------------------------------------------------------------------------


def test_create_card_adds_card_to_list() -> None:
    fake_planka = _make_fake_planka()
    adapter = PlankaAdapter(planka=fake_planka)  # type: ignore[arg-type]

    new_card = adapter.create_card(list_id="l-1", name="New Task", description="desc")

    assert isinstance(new_card, PlankaCard)
    assert new_card.name == "New Task"
    assert new_card.list_id == "l-1"
    assert new_card.board_id == "b-1"


def test_create_card_raises_for_unknown_list() -> None:
    adapter = PlankaAdapter(planka=_make_fake_planka())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="List 'l-999' not found"):
        adapter.create_card(list_id="l-999", name="Orphan")


def test_create_card_without_description() -> None:
    adapter = PlankaAdapter(planka=_make_fake_planka())  # type: ignore[arg-type]
    card = adapter.create_card(list_id="l-2", name="Minimal")
    assert card.name == "Minimal"


# ---------------------------------------------------------------------------
# move_card
# ---------------------------------------------------------------------------


def test_move_card_updates_list_id() -> None:
    adapter = PlankaAdapter(planka=_make_fake_planka())  # type: ignore[arg-type]

    moved = adapter.move_card(card_id="c-1", list_id="l-2")

    assert isinstance(moved, PlankaCard)
    assert moved.list_id == "l-2"


def test_move_card_raises_for_unknown_card() -> None:
    adapter = PlankaAdapter(planka=_make_fake_planka())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Card 'bad-card' not found"):
        adapter.move_card(card_id="bad-card", list_id="l-2")


def test_move_card_raises_for_unknown_list() -> None:
    adapter = PlankaAdapter(planka=_make_fake_planka())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="List 'bad-list' not found"):
        adapter.move_card(card_id="c-1", list_id="bad-list")


# ---------------------------------------------------------------------------
# add_comment
# ---------------------------------------------------------------------------


def test_add_comment_calls_plankapy_add_comment() -> None:
    fake_planka = _make_fake_planka()
    adapter = PlankaAdapter(planka=fake_planka)  # type: ignore[arg-type]

    adapter.add_comment(card_id="c-1", text="Work started.")

    # Verify comment was recorded on the underlying fake card
    board = fake_planka.projects[0].boards[0]
    raw_card = next(c for c in board._cards if c.id == "c-1")
    assert "Work started." in raw_card._comments


def test_add_comment_raises_for_unknown_card() -> None:
    adapter = PlankaAdapter(planka=_make_fake_planka())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Card 'nope' not found"):
        adapter.add_comment(card_id="nope", text="Hi")


# ---------------------------------------------------------------------------
# from_env
# ---------------------------------------------------------------------------


def test_from_env_raises_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLANKA_BASE_URL", raising=False)
    monkeypatch.delenv("PLANKA_API_TOKEN", raising=False)

    with pytest.raises(ValueError, match="PLANKA_BASE_URL"):
        PlankaAdapter.from_env()


def test_from_env_raises_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLANKA_BASE_URL", "http://localhost:3000")
    monkeypatch.delenv("PLANKA_API_TOKEN", raising=False)

    with pytest.raises(ValueError, match="PLANKA_API_TOKEN"):
        PlankaAdapter.from_env()


def test_from_env_raises_when_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLANKA_BASE_URL", raising=False)
    monkeypatch.setenv("PLANKA_API_TOKEN", "tok-123")

    with pytest.raises(ValueError, match="PLANKA_BASE_URL"):
        PlankaAdapter.from_env()


@patch("src.cyberagent.integrations.planka.adapter.Planka")
@patch("src.cyberagent.integrations.planka.adapter.TokenAuth")
def test_from_env_constructs_adapter(
    mock_token_auth: MagicMock,
    mock_planka: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLANKA_BASE_URL", "http://planka.example.com")
    monkeypatch.setenv("PLANKA_API_TOKEN", "secret-tok")

    mock_auth_instance = MagicMock()
    mock_token_auth.return_value = mock_auth_instance
    mock_planka_instance = MagicMock()
    mock_planka.return_value = mock_planka_instance

    adapter = PlankaAdapter.from_env()

    mock_token_auth.assert_called_once_with("secret-tok")
    mock_planka.assert_called_once_with("http://planka.example.com", mock_auth_instance)
    assert isinstance(adapter, PlankaAdapter)
