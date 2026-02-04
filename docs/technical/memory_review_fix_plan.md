# Memory Review Fix Plan

## Goals
1. Address review findings for memory CRUD and tool exposure.
2. Close test gaps for default backend behavior and tool bulk limits.
3. Align storage paths with security policy (all data under `data/`).

## Phase 1: Safety & Permissions
1. Gate `memory_crud` behind skill permissions or an explicit allowlist.
2. Add deny-by-default for teams/systems without grants.
3. Add tests to ensure tool availability respects grants.

## Phase 2: Backend Capability Handling
1. For `list` backend, handle `NotImplementedError` from update/delete.
2. Decide behavior: return `INVALID_PARAMS` or `NOT_IMPLEMENTED`.
3. Add tests that update/delete return structured errors when backend lacks support.

## Phase 3: Bulk Limits & Validation
1. Enforce `MAX_BULK_ITEMS` for `read` and `promote`.
2. Add tests for bulk limit exceedance on `read`/`promote`.

## Phase 4: Storage Policy Alignment
1. Update default memory storage paths to live under `data/`.
2. Ensure Chroma persistence path respects `data/` by default.
3. Add tests for default config paths.

## Phase 5: Observability Wiring
1. Decide default audit sink/metrics wiring for CLI usage.
2. Add tests that verify audit events emit when configured.

## Deliverables
1. Code fixes across memory tool, config, and permissions.
2. New/updated unit tests under `tests/memory/`.
3. Updated feature/doc references if behavior changes.
