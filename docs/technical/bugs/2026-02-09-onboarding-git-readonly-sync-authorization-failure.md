# Bug: Onboarding PKM Sync Fails Due to Tool Authorization

## Date
2026-02-09

## Status
Open

## Summary
Onboarding PKM sync fails when the onboarding flow attempts to run `git-readonly-sync` as agent `System4/root`, but RBAC denies tool execution. Users then see:

- `Failed to sync onboarding repo: Agent System4/root not authorized to use git-readonly-sync`
- `We couldn't sync your PKM vault.`

## Observed Behavior
- Private GitHub PKM vault sync does not complete during onboarding.
- Onboarding continues without PKM context, which degrades discovery quality.

## Expected Behavior
- `System4/root` should be authorized to run `git-readonly-sync` during onboarding PKM sync.
- PKM sync should complete (or fail only for operational causes like token/network/repo access issues).

## Verified Technical Evidence
- On onboarding repo sync failure, the flow prints `Failed to sync onboarding repo: {error}` from `src/cyberagent/cli/messages.json:117`.
- The user-facing fallback message `We couldn't sync your PKM vault.` is defined in `src/cyberagent/cli/messages.json:112`.
- CLI tool execution denies unauthorized tool use with:
  `Agent {agent_id} not authorized to use {tool_name}` in `src/cyberagent/tools/cli_executor/cli_tool.py:62`.
- Onboarding sync calls `git-readonly-sync` with the onboarding agent ID (expected `System4/root`) in `src/cyberagent/cli/onboarding_discovery.py:360`.
- Tests confirm onboarding sync is invoked as `System4/root` in `tests/cli/test_onboarding_discovery.py:664`.

## Suspected Root Cause
RBAC policy does not include (or does not correctly evaluate) permission for `System4/root` to execute `git-readonly-sync`.

## Reproduction
1. Start onboarding with `pkm_source=github` and a repo URL.
2. Reach onboarding discovery PKM sync step.
3. Observe sync failure with authorization error for `System4/root` and fallback message about PKM vault sync failure.

## Impact
- Onboarding misses PKM-derived context.
- Higher risk of low-quality onboarding interview outputs and less personalized follow-up questions.

## Proposed Fix
1. Add/verify RBAC permission allowing `System4/root` (or the appropriate System4 role) to execute `git-readonly-sync`.
2. Add/extend tests to assert this permission is present in onboarding runtime conditions.
3. Keep denial behavior unchanged for agents outside onboarding scope.

