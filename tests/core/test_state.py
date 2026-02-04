from __future__ import annotations

from sqlalchemy.exc import OperationalError

from src.cyberagent.core import state


class _FakeSession:
    def __init__(self, commit_errors: list[Exception]) -> None:
        self._commit_errors = commit_errors
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1
        if self._commit_errors:
            raise self._commit_errors.pop(0)

    def rollback(self) -> None:
        self.rollbacks += 1


def test_commit_with_recovery_retries_on_disk_io(monkeypatch) -> None:
    fake = _FakeSession(
        commit_errors=[
            OperationalError("disk I/O error", None, Exception("disk I/O error")),
        ]
    )
    monkeypatch.setattr(state, "recover_sqlite_database", lambda: "backup.db")

    state._commit_with_recovery(fake, "mark_team_active")

    assert fake.commits == 2
    assert fake.rollbacks >= 1


def test_commit_with_recovery_logs_and_returns_on_other_errors(monkeypatch) -> None:
    fake = _FakeSession(
        commit_errors=[OperationalError("locked", None, Exception("locked"))]
    )
    monkeypatch.setattr(state, "recover_sqlite_database", lambda: None)

    state._commit_with_recovery(fake, "mark_team_active")

    assert fake.commits == 1
    assert fake.rollbacks == 1
