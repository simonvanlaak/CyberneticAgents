# Task Flows

## Overview
This document is the canonical discussion surface for the full task lifecycle:
- status transitions
- execution and review loops
- rejection handling and restart paths
- follow-up task linkage

It reflects the current implementation and highlights places where behavior can be evolved.

## Lifecycle State Machine
Current transitions (from `ALLOWED_TASK_TRANSITIONS`) are:
- `pending -> in_progress | canceled`
- `in_progress -> completed | blocked`
- `blocked -> in_progress | canceled`
- `completed -> approved | rejected`
- `rejected -> pending | canceled`
- `approved` is terminal
- `canceled` is terminal

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> in_progress
    pending --> canceled

    in_progress --> completed
    in_progress --> blocked

    blocked --> in_progress
    blocked --> canceled

    completed --> approved
    completed --> rejected

    rejected --> pending
    rejected --> canceled

    approved --> [*]
    canceled --> [*]
```

## End-To-End Runtime Flow
```mermaid
flowchart TB
 subgraph S1S["System1 Scope (Operations)"]
        A1["System1 sets task status to in_progress"]
        B["System1 executes"]
        C{"System1 result contract"}
        D["Task -> completed"]
        E["Task -> blocked"]
  end
 subgraph S3S["System3 Scope (Control)"]
        A01["System4 -> System3: InitiativeAssignMessage"]
        A02{"Tasks already exist for initiative?"}
        A03["System3 creates task records"]
        A04["New tasks start as pending"]
        A05["System3 picks next existing task"]
        A["System3 assigns task"]
        NX2{"Next task available?"}
        NX3["System3 assigns next task in initiative"]
        NX4["No remaining tasks in initiative"]
        IR1["System3 -> System4: InitiativeReviewMessage"]
        F["System3 task review"]
        G{"Task status review-eligible?"}
        H["Error: invalid review status for TaskReviewMessage"]
        H2["System3 resets task status to pending"]
        I{"Blocked or Completed path"}
        J0["System3 enters blocked-resolution loop"]
        J1{"Blocked-resolution action"}
        J3["System3 modifies task"]
        J4["System3 sets task status to pending and restarts execution"]
        M["Policy judgement cases"]
        N{"Outcome"}
        O["Task -> approved"]
        P1["System3 -> System5: PolicyVagueMessage"]
        P3["System5 -> System3: TaskReviewMessage"]
        P4["System3 reruns policy review"]
        Q["Task -> rejected"]
        R{"Rejection handling decision"}
        R0["System3 compiles rejection evidence"]
        R1["System3 -> System5: remediation request"]
        L["Task -> canceled"]
        NX1["System3 checks remaining tasks in initiative"]
        S1S
  end
 subgraph S4S["System4 Scope (Intelligence)"]
        A0["System4 selects/starts initiative"]
        J2["System3 -> System4: request_research_tool"]
        IR2["System4 reviews completed initiative and selects next initiative"]
        S3S
  end
 subgraph S5S["System5 Scope (Policy Supervision)"]
        S4S
        P2["System5 clarifies or updates policy"]
        H1["System3 -> System5: InternalErrorMessage"]
        R2{"System5 remediation outcome"}
        R21["System5 action: update System1 config/skills"]
        R22["System5 action: authorize new System1 profile"]
        R011["System5 -> User: escalation"]
  end
 subgraph US["User Scope (External)"]
        U1["User notified / manual intervention"]
  end
    J3 --> J4
    A0 --> A01
    A01 --> A02
    A02 -- no --> A03
    A03 --> A04
    A04 --> A
    A02 -- yes --> A05
    A05 --> A
    A --> A1
    A1 --> B
    B --> C
    C -- "status=done" --> D
    C -- "status=blocked" --> E
    D --> F
    E --> F
    F --> G
    G -- no --> H
    H --> H1 & H2
    H2 --> A
    G -- yes --> I
    I -- blocked --> J0
    J0 --> J1
    J1 -- request research --> J2
    J2 --> J3
    J1 -- System1 not equipped --> R1
    J1 -- modify and restart directly --> J3
    J4 --> A
    J1 -- cancel --> L
    I -- completed --> M
    M --> N
    N -- all satisfied --> O
    N -- any vague --> P1
    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> F
    N -- violated and no vague --> Q
    O --> NX1
    L --> NX1
    NX1 --> NX2
    NX2 -- yes --> NX3
    NX3 --> A05
    NX2 -- no --> NX4
    NX4 --> IR1
    IR1 --> IR2
    IR2 --> A01
    Q --> R
    R -- Existing System1 with better information/prompt --> J1
    R -- System1 change required --> R0
    R0 --> R1
    R1 --> R2
    R2 -- System1 config/skills updated --> R21
    R2 -- New System1 profile authorized --> R22
    R21 --> J4
    R22 --> J4
    R2 -- No viable remediation --> R011
    R011 --> U1
    U1 --> L
```

## Vague Clarification Loop (System3 <-> System5)
When review produces one or more `Vague` cases, the task stays `completed` while
System3 and System5 resolve policy ambiguity and retrigger review.

```mermaid
sequenceDiagram
    participant S3 as System3
    participant T as Task Record
    participant S5 as System5

    S3->>T: Task is completed
    S3->>S5: PolicyVagueMessage(task_id, policy_id, reasoning)
    S5->>S5: Clarify/update ambiguous policy wording
    S5->>S3: TaskReviewMessage(task_id, assignee, content)
    S3->>S3: Re-run policy judgement
    S3->>T: Keep status completed until no Vague cases
```

## Task Creation And Initial Assignment
- Task creation starts from an initiative assignment to System3.
- If no tasks exist for the initiative, System3 creates task records.
- Newly created tasks start in `pending`.
- System3 selects the next task and assigns it to System1.
- On assignment handling, System1 moves the task to `in_progress` before execution.
- After each task ends in `approved` or `canceled`, System3 checks for remaining
  tasks in the same initiative and assigns the next one.
- If no tasks remain, System3 sends `InitiativeReviewMessage` to System4 for
  initiative review and next-initiative selection.

## Status Semantics
- `pending`: backlog state for an already-defined task, ready to be assigned.
- `in_progress`: task is actively being executed by System1.
- `blocked`: System1 could not complete task with current context/capability.
- `completed`: System1 returned done-result; waiting for/under review outcome.
- `approved`: completed output satisfied policies; terminal success.
- `rejected`: completed output failed policy review; requires rework or cancellation decision.
- `canceled`: terminal stop state when work should not continue on this task.

## Review Contract
- Review-eligible statuses are `completed` and `blocked`.
- If a `TaskReviewMessage` is received for any other status, System3 should
  treat it as an internal error, route it to System5, reset task status to
  `pending`, and continue with assignment.
- `completed` path:
  - all cases `Satisfied` -> `approved`
  - any case `Vague` -> remain `completed` and request clarification/review retry
  - no vague and at least one `Violated` -> `rejected`
- `blocked` path:
  - System3 executes blocked-resolution flow (research/modify/restart)
  - if blocked-resolution determines System1 is not equipped, System3 sends
    a remediation request to System5 and continues via `System5 remediation outcome`
  - task can return to `in_progress` or end as `canceled`

## Rejected Task Flow
After a task is `rejected`, handling should be:
- choose one of two paths:
  - existing System1 can solve it with improved information/prompt
  - System1 change is required (capability/config/profile remediation via System5)

If replacement work is created, the flow should:
- compile structured rejection evidence from case judgements and execution traces
- request System5 remediation before replacement assignment
  - System5 may update current System1 config/skills
  - or authorize a better-equipped System1 profile
- only System5 escalates to user when no viable remediation exists
- move the original task to `canceled`
- link replacement task IDs on the original via `follow_up_task_ids`
- route into the task-creation path (`System3 creates task records`)

## Follow-Up Task Linking
- Field: `tasks.follow_up_task_ids` (JSON list of integer task IDs)
- Purpose: lineage between original task and replacement/follow-up tasks
- Expected usage:
  - when a rejected task is replaced, append the new task ID(s) to the original
  - keep the original task as historical record (`rejected` or `canceled`)

## Discussion Topics
Use this section to align desired behavior before further code changes:
- Should System3 always create follow-up tasks on cancellation, or only for selected rejection scenarios?
- Should initiative progression depend on all tasks being terminal (`approved|canceled`)?
