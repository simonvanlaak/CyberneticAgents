"""Thin Planka adapter using plankapy (issue #132).

Auth: API token via PLANKA_API_TOKEN env var.
No shell-outs; plankapy is called directly from Python.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from plankapy import Planka, TokenAuth  # type: ignore[import-untyped]


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlankaBoard:
    """Minimal board projection."""

    board_id: str
    name: str
    project_id: str


@dataclass(frozen=True)
class PlankaList:
    """Minimal list projection."""

    list_id: str
    name: str
    board_id: str


@dataclass(frozen=True)
class PlankaCard:
    """Minimal card projection."""

    card_id: str
    name: str
    list_id: str
    board_id: str
    description: str = ""


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class PlankaAdapter:
    """Thin Planka adapter for board/list/card operations.

    Wraps plankapy's ``Planka`` client. Inject a ``planka`` instance for
    testing or use ``from_env()`` for production.

    Environment variables (``from_env``):
        PLANKA_BASE_URL   - Base URL of the Planka instance (e.g. http://localhost:3000)
        PLANKA_API_TOKEN  - API token for authentication
    """

    def __init__(self, planka: Any) -> None:
        self._planka = planka

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "PlankaAdapter":
        """Construct adapter from environment variables.

        Raises:
            ValueError: If required environment variables are missing.
        """
        base_url = os.getenv("PLANKA_BASE_URL", "").strip()
        api_token = os.getenv("PLANKA_API_TOKEN", "").strip()

        missing: list[str] = []
        if not base_url:
            missing.append("PLANKA_BASE_URL")
        if not api_token:
            missing.append("PLANKA_API_TOKEN")
        if missing:
            raise ValueError(
                f"Missing required Planka configuration: {', '.join(missing)}"
            )

        auth = TokenAuth(api_token)
        planka = Planka(base_url, auth)
        return cls(planka)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def list_boards(self) -> list[PlankaBoard]:
        """Return all boards visible to the authenticated bot user."""
        boards: list[PlankaBoard] = []
        for project in self._planka.projects:
            for board in project.boards:
                boards.append(
                    PlankaBoard(
                        board_id=str(board.id),
                        name=str(board.name),
                        project_id=str(project.id),
                    )
                )
        return boards

    def list_lists(self, board_id: str) -> list[PlankaList]:
        """Return all lists in the given board.

        Args:
            board_id: ID of the target board.

        Raises:
            ValueError: If the board is not found.
        """
        board = self._find_board(board_id)
        return [
            PlankaList(
                list_id=str(lst.id),
                name=str(lst.name),
                board_id=str(lst.boardId),
            )
            for lst in board.lists
        ]

    def list_cards(self, board_id: str) -> list[PlankaCard]:
        """Return all cards on the given board.

        Args:
            board_id: ID of the target board.

        Raises:
            ValueError: If the board is not found.
        """
        board = self._find_board(board_id)
        return [
            PlankaCard(
                card_id=str(card.id),
                name=str(card.name),
                list_id=str(card.listId),
                board_id=str(card.boardId),
                description=str(card.description) if card.description else "",
            )
            for card in board.cards
        ]

    def get_card(self, card_id: str) -> PlankaCard:
        """Fetch a card by its ID (searches all visible boards).

        Args:
            card_id: ID of the card to fetch.

        Raises:
            ValueError: If the card is not found.
        """
        raw = self._find_raw_card(card_id)
        return PlankaCard(
            card_id=str(raw.id),
            name=str(raw.name),
            list_id=str(raw.listId),
            board_id=str(raw.boardId),
            description=str(raw.description) if raw.description else "",
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create_card(
        self,
        list_id: str,
        name: str,
        description: str = "",
    ) -> PlankaCard:
        """Create a card in the specified list.

        Args:
            list_id:     ID of the target list.
            name:        Card title.
            description: Optional card body.

        Raises:
            ValueError: If the list is not found.

        Returns:
            Projection of the newly created card.
        """
        raw_list = self._find_raw_list(list_id)
        raw_card = raw_list.create_card(name=name, description=description)
        return PlankaCard(
            card_id=str(raw_card.id),
            name=str(raw_card.name),
            list_id=str(raw_card.listId),
            board_id=str(raw_card.boardId),
            description=str(raw_card.description) if raw_card.description else "",
        )

    def move_card(self, card_id: str, list_id: str) -> PlankaCard:
        """Move a card to a different list by IDs.

        Args:
            card_id: ID of the card to move.
            list_id: ID of the destination list.

        Raises:
            ValueError: If the card or list is not found.

        Returns:
            Updated card projection.
        """
        raw_card = self._find_raw_card(card_id)
        raw_list = self._find_raw_list(list_id)
        raw_card.move(raw_list)
        return PlankaCard(
            card_id=str(raw_card.id),
            name=str(raw_card.name),
            list_id=str(raw_card.listId),
            board_id=str(raw_card.boardId),
            description=str(raw_card.description) if raw_card.description else "",
        )

    def add_comment(self, card_id: str, text: str) -> None:
        """Append a comment to a card.

        Args:
            card_id: ID of the target card.
            text:    Comment body.

        Raises:
            ValueError: If the card is not found.
        """
        raw_card = self._find_raw_card(card_id)
        raw_card.add_comment(text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_board(self, board_id: str) -> Any:
        """Locate a board object across all projects.

        Raises:
            ValueError: If the board is not found.
        """
        for project in self._planka.projects:
            for board in project.boards:
                if str(board.id) == board_id:
                    return board
        raise ValueError(f"Board '{board_id}' not found.")

    def _find_raw_list(self, list_id: str) -> Any:
        """Locate a list object across all boards.

        Raises:
            ValueError: If the list is not found.
        """
        for project in self._planka.projects:
            for board in project.boards:
                for lst in board.lists:
                    if str(lst.id) == list_id:
                        return lst
        raise ValueError(f"List '{list_id}' not found.")

    def _find_raw_card(self, card_id: str) -> Any:
        """Locate a raw plankapy card across all boards.

        Raises:
            ValueError: If the card is not found.
        """
        for project in self._planka.projects:
            for board in project.boards:
                for card in board.cards:
                    if str(card.id) == card_id:
                        return card
        raise ValueError(f"Card '{card_id}' not found.")
