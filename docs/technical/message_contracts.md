# Message Contracts: System3 ↔ System5

This document defines explicit payload contracts for deterministic orchestration in task-flow remediation paths.

## Scope

The contracts below cover:
- invalid-review recovery
- blocked remediation
- rejected replacement/remediation request
- rejected-task remediation approval trigger

## 1) Invalid Review Recovery Contract

**Carrier message:** `InternalErrorMessage.contract`

**Model:** `InvalidReviewRecoveryContract`

Fields:
- `task_id` (int)
- `initiative_id` (int | null)
- `observed_status` (str)
- `retry_count` (int)
- `retry_limit` (int)
- `error_summary` (str)
- `next_action` (str)

Current `next_action` values:
- `auto_retry_assignment`
- `wait_for_policy_remediation`

## 2) Blocked Remediation Contract

**Carrier message:** `CapabilityGapMessage.contract`

**Model:** `BlockedRemediationContract`

Fields:
- `task_id` (int)
- `initiative_id` (int | null)
- `assignee_agent_id_str` (str)
- `blocked_reasoning` (str)
- `remediation_request` (str)

## 3) Rejected Replacement / Remediation Contract

**Carrier message:** `PolicyViolationMessage.contract`

**Model:** `RejectedReplacementContract`

Fields:
- `task_id` (int)
- `initiative_id` (int | null)
- `assignee_agent_id_str` (str)
- `policy_id` (int)
- `policy_reasoning` (str)
- `case_judgement` (str | null)
- `execution_log` (str | null)
- `requested_outcome` (str)

Current `requested_outcome` value:
- `create_replacement_or_remediate`

## 4) Rejected-Task Remediation Approval Contract

**Carrier message:** `RejectedTaskRemediationApprovedMessage.contract`

**Model:** `RejectedTaskRemediationApprovalContract`

Fields:
- `task_id` (int)
- `initiative_id` (int | null)
- `policy_id` (int)
- `policy_reasoning` (str)
- `approved_changes` (str)

Notes:
- This is the explicit System5 -> System3 unlock signal for replacement creation.
- System3 must not create replacement tasks until this contract-bearing message is received.

## Validation

All contract models are strict (`extra="forbid"`) and are test-covered in `tests/agents/test_system3.py`.