# SQLite Disk I/O Errors (Test DB)

## Summary
While running tests, SQLite frequently raises `disk I/O error` during database
initialization. This blocks test runs and appears to be environmental rather
than a code-path regression.

## Symptoms
- Failures occur during `init_db.init_db()` while executing
  `Base.metadata.create_all`.
- Error example (from `pytest`):
  - `sqlite3.OperationalError: disk I/O error`
  - Fails on DDL like `CREATE TABLE routing_rules` or `CREATE INDEX ...`
- Retrying after deleting `.pytest_db/test.db` still fails.

## Reproduction (Recent)
Command:
```bash
python3 -m pytest tests/services/test_routing.py -v
```

Observed error:
```
sqlite3.OperationalError: disk I/O error
RuntimeError: SQLite disk I/O error while initializing database at
/home/simon/Projects/2025/CyberneticAgents/.pytest_db/test.db.
```

## Environment Notes
- Test DB path: `.pytest_db/test.db`
- Configuration happens in `tests/conftest.py` using
  `init_db.configure_database(f"sqlite:///{db_path}")`.

## Attempts
- Deleted `.pytest_db/test.db` and reran tests.
  - Error persisted.

## Open Questions / Next Steps
- Check filesystem permissions and disk space.
- Verify whether concurrent processes are locking the file.
- Consider switching test DB to `:memory:` or a temp dir to isolate issues.
- Add explicit logging around `_ensure_db_writable()` and sqlite errors.

## Resolution (Recommended)
Use per-worker SQLite files for pytest runs to avoid cross-process contention.
We now derive a unique worker id from `PYTEST_XDIST_WORKER` (e.g. `gw0`)
and fall back to the current PID when xdist is not active. Test DBs live
under `.pytest_db/<worker_id>/` (including `skill_permissions.db`), so
parallel agents and xdist workers never share a single SQLite file.
