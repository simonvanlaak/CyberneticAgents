# Testing Strategy Issues And Resolution Plan

## Context
This document records current testing strategy gaps, their impact, and the
plan we are executing to resolve them. The focus is on stability as the
suite grows and on ensuring that concurrency does not hide regressions.

## Issues
1. Background thread failures are only reported as warnings.
   - Impact: real failures can be missed because tests still pass.
   - Observed in onboarding discovery threads during CLI tests.
2. Global DB initialization uses `pytest_configure()` rather than fixtures.
   - Impact: global setup makes isolation and teardown less explicit.
3. Test DB cleanup is partial.
   - Impact: data from earlier tests can leak into later tests.
4. Parallel test guidance is implicit rather than enforced.
   - Impact: different agents can end up running tests in slightly different ways.

## Resolution Plan (Implemented In This Change)
1. Fail tests on background thread exceptions.
   - Add a thread exception tracker and a pytest fixture that raises after each test.
2. Make onboarding discovery background threads opt-out during tests.
   - Add a `CYBERAGENT_DISABLE_BACKGROUND_DISCOVERY` guard and set it in tests.
3. Convert DB setup to a session-scoped fixture.
   - Replace `pytest_configure()` with a session fixture for explicit setup.

## Follow-Up (Tracked For Next Iteration)
1. Full DB reset per test or per module.
   - Decide between truncation or transactional isolation.
2. Explicit parallel test guidance in `pyproject.toml` / CI.
   - Add a standard xdist command and document it in the test docs.
