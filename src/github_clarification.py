from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


CLARIFICATION_REQUEST_MARKER = "CLARIFICATION_REQUEST:"
CLARIFIED_MARKER = "CLARIFIED:"


@dataclass(frozen=True)
class Comment:
    id: int
    author: str
    body: str


@dataclass(frozen=True)
class ClarificationState:
    request_comment_id: Optional[int]
    clarified: bool


def compute_clarification_state(comments: Iterable[Comment], *, owner_login: str) -> ClarificationState:
    """Compute whether a clarification request has been answered.

    Protocol:
    - A clarification request is any comment whose body contains CLARIFICATION_REQUEST_MARKER.
    - It is considered answered if there exists a later comment authored by `owner_login`
      whose body contains CLARIFIED_MARKER.

    Args:
        comments: Comments in chronological order.
        owner_login: Repo owner GitHub login.

    Returns:
        ClarificationState.
    """

    last_request: Optional[Comment] = None
    after_request: list[Comment] = []

    for c in comments:
        if CLARIFICATION_REQUEST_MARKER in (c.body or ""):
            last_request = c
            after_request = []
            continue
        if last_request is not None:
            after_request.append(c)

    if last_request is None:
        return ClarificationState(request_comment_id=None, clarified=True)

    clarified = any(
        (c.author == owner_login) and (CLARIFIED_MARKER in (c.body or ""))
        for c in after_request
    )

    return ClarificationState(request_comment_id=last_request.id, clarified=clarified)
