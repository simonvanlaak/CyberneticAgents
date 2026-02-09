# Testing Strategy Issues And Resolution Plan

## Context
This document records current testing strategy gaps, their impact, and the
plan we are executing to resolve them. The focus is on stability as the
suite grows and on ensuring that concurrency does not hide regressions.

## Status (2026-02-09)
All originally tracked issues are resolved.

## Resolved Issues
1. Background thread failures no longer hide failures.
   - Implemented via thread exception tracker + autouse guard fixture.
2. Global DB initialization no longer relies on `pytest_configure()`.
   - Implemented via explicit session-scoped fixture in `tests/conftest.py`.
3. Test DB cleanup now has regression coverage for per-test isolation.
   - Verified by `tests/test_db_isolation.py`.
4. Parallel test strategy is now explicit and enforced.
   - Standard command documented in `tests/README.md`.
   - CI workflow enforces parallel execution in `.github/workflows/tests-parallel.yml`.

## Notes
- Worker-specific SQLite databases remain in use under `.pytest_db/<worker_id>/`.
- Onboarding background discovery remains disabled during tests via
  `CYBERAGENT_DISABLE_BACKGROUND_DISCOVERY=1`.
