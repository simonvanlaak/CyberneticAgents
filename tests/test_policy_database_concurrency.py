import multiprocessing
import os
import tempfile
from pathlib import Path


def _init_worker(db_url: str, q: multiprocessing.Queue) -> None:
    try:
        os.environ["CYBERAGENT_DB_URL"] = db_url
        # Import after env is set so module picks up the URL.
        from src import policy_database

        policy_database.init_database()
        q.put((True, None))
    except Exception as exc:  # pragma: no cover
        q.put((False, repr(exc)))


def test_init_database_is_safe_under_concurrent_calls() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "shared.db"
        db_url = f"sqlite:///{db_path}"

        q: multiprocessing.Queue = multiprocessing.Queue()
        p1 = multiprocessing.Process(target=_init_worker, args=(db_url, q))
        p2 = multiprocessing.Process(target=_init_worker, args=(db_url, q))

        p1.start()
        p2.start()
        p1.join(timeout=20)
        p2.join(timeout=20)

        r1 = q.get(timeout=5)
        r2 = q.get(timeout=5)

        assert r1[0] is True, r1
        assert r2[0] is True, r2
