from __future__ import annotations

from src.cyberagent.testing.pytest_worker import get_pytest_worker_id


def test_get_pytest_worker_id_prefers_xdist_worker() -> None:
    worker_id = get_pytest_worker_id({"PYTEST_XDIST_WORKER": "gw3"}, 4242)
    assert worker_id == "gw3"


def test_get_pytest_worker_id_falls_back_to_pid() -> None:
    worker_id = get_pytest_worker_id({}, 4242)
    assert worker_id == "pid4242"
