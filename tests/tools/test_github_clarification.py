from __future__ import annotations

from src.github_clarification import (
    CLARIFICATION_REQUEST_MARKER,
    CLARIFIED_MARKER,
    Comment,
    compute_clarification_state,
)


def test_no_request_means_clarified() -> None:
    state = compute_clarification_state([], owner_login="simon")
    assert state.request_comment_id is None
    assert state.clarified is True


def test_request_without_owner_reply_is_not_clarified() -> None:
    comments = [
        Comment(id=1, author="bot", body=f"{CLARIFICATION_REQUEST_MARKER} q1"),
        Comment(id=2, author="someone", body="ok"),
    ]
    state = compute_clarification_state(comments, owner_login="simon")
    assert state.request_comment_id == 1
    assert state.clarified is False


def test_owner_reply_with_marker_clarifies() -> None:
    comments = [
        Comment(id=1, author="bot", body=f"{CLARIFICATION_REQUEST_MARKER} q1"),
        Comment(id=2, author="simon", body=f"{CLARIFIED_MARKER} a1"),
    ]
    state = compute_clarification_state(comments, owner_login="simon")
    assert state.request_comment_id == 1
    assert state.clarified is True


def test_only_latest_request_counts() -> None:
    comments = [
        Comment(id=1, author="bot", body=f"{CLARIFICATION_REQUEST_MARKER} old"),
        Comment(id=2, author="simon", body=f"{CLARIFIED_MARKER} old answer"),
        Comment(id=3, author="bot", body=f"{CLARIFICATION_REQUEST_MARKER} new"),
        Comment(id=4, author="someone", body="noise"),
    ]
    state = compute_clarification_state(comments, owner_login="simon")
    assert state.request_comment_id == 3
    assert state.clarified is False
