"""Deterministic Casbin policy bootstrap/version helpers."""

from __future__ import annotations

from typing import Iterable

import casbin

BOOTSTRAP_SUBJECT = "__cyberagent_bootstrap__"
BOOTSTRAP_RESOURCE = "policy_version"
BOOTSTRAP_VERSION = "2026-02-09-v1"


def ensure_policy_bootstrap(enforcer: casbin.Enforcer, scope: str) -> None:
    """
    Ensure deterministic policy bootstrap marker exists for a policy scope.

    The marker provides an explicit policy version so future migrations can
    deterministically detect and upgrade authorization baselines.
    """
    enforcer.load_policy()
    marker = [BOOTSTRAP_SUBJECT, scope, BOOTSTRAP_RESOURCE, BOOTSTRAP_VERSION]
    if enforcer.has_policy(*marker):
        return

    _remove_outdated_markers(enforcer=enforcer, scope=scope)
    enforcer.add_policy(*marker)
    enforcer.save_policy()


def _remove_outdated_markers(enforcer: casbin.Enforcer, scope: str) -> None:
    policies = enforcer.get_filtered_policy(0, BOOTSTRAP_SUBJECT)
    for policy in policies:
        if not _is_marker_for_scope(policy=policy, scope=scope):
            continue
        if len(policy) >= 4 and policy[3] == BOOTSTRAP_VERSION:
            continue
        enforcer.remove_policy(*policy)


def _is_marker_for_scope(policy: Iterable[str], scope: str) -> bool:
    parts = list(policy)
    if len(parts) < 4:
        return False
    return parts[1] == scope and parts[2] == BOOTSTRAP_RESOURCE
