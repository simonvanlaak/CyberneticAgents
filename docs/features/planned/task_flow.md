# Task Flows

## Overview
This document is the canonical discussion surface for the full task lifecycle:
- status transitions
- execution and review loops
- rejection handling and replacement-attempt lineage
- initiative progression and review gates

This document now reflects the intended target behavior for implementation.

## Lifecycle State Machine
Target transitions (single task record) are:
- `pending -> in_progress | canceled`
- `in_progress -> completed | blocked`
- `blocked -> in_progress | canceled`
- `completed -> approved | rejected`
- `rejected -> canceled`
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
        A05["System3 picks next existing pending task"]
        A["System3 selects best suited System1 to assign task to"]

        F["System3 task review"]
        G{"Task status review-eligible?"}
        H["Error: invalid review status for TaskReviewMessage"]
        H3{"Invalid-review auto-retry count < 3?"}
        H2["System3 resets task status to pending and clears assignee"]
        H4["System3 stops auto-retry and waits for System5 remediation"]

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
        RR1["System3 prepares improved replacement task spec"]
        R0["System3 compiles rejection evidence"]
        R1["System3 -> System5: remediation request"]

        RC["Task -> canceled (archive rejected attempt)"]
        T1["System3 creates replacement task (same initiative)"]
        T2["Replacement task starts as pending"]
        T3["Original.follow_up_task_ids += replacement_task_id"]
        T4["Replacement.replaces_task_id = original_task_id"]

        L["Task -> canceled"]

        NX1["System3 inspects initiative task states"]
        NX2{"All tasks terminal (approved|canceled)?"}
        NX3{"Any pending tasks to assign?"}
        NX4["No remaining tasks in initiative"]
        NX5["System3 waits for active in_progress/blocked tasks"]
        NX6["System3 assigns next pending task in initiative"]
        IR1["System3 -> System4: InitiativeReviewMessage"]
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
    C -- status=done --> D
    C -- status=blocked --> E

    D --> F
    E --> F

    F --> G
    G -- no --> H
    H --> H3
    H3 -- yes --> H1
    H3 -- yes --> H2
    H2 --> A05
    H3 -- no --> H1
    H3 -- no --> H4

    G -- yes --> I
    I -- blocked --> J0
    J0 --> J1
    J1 -- request research --> J2
    J2 --> J3
    J1 -- modify and restart directly --> J3
    J3 --> J4
    J4 --> A05
    J1 -- System1 not equipped --> R1
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

    Q --> R
    R -- existing System1 can pass with better information/prompt --> RR1
    R -- System1 change required --> R0
    RR1 --> RC
    R0 --> R1
    R1 --> R2
    R2 -- System1 config/skills updated --> R21
    R2 -- New System1 profile authorized --> R22
    R21 --> RC
    R22 --> RC
    R2 -- No viable remediation --> R011
    R011 --> U1
    U1 --> L

    RC --> T1
    T1 --> T2
    T2 --> T3
    T3 --> T4
    T4 --> A05

    O --> NX1
    L --> NX1
    NX1 --> NX2
    NX2 -- yes --> NX4
    NX4 --> IR1
    IR1 --> IR2
    IR2 --> A01
    NX2 -- no --> NX3
    NX3 -- yes --> NX6
    NX6 --> A05
    NX3 -- no --> NX5
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
- System3 selects the next pending task, then selects the best-suited System1, then assigns.
- On assignment handling, System1 moves the task to `in_progress` before execution.
- After each `approved` or `canceled` outcome, System3 checks initiative task states:
  - if pending tasks exist, assign the next pending task
  - if no pending tasks but non-terminal tasks exist, wait
  - if all tasks are terminal (`approved|canceled`), send `InitiativeReviewMessage` to System4

## Status Semantics
- `pending`: backlog state for a defined task, ready for assignment.
- `in_progress`: task is actively being executed by System1.
- `blocked`: System1 could not complete task with current context/capability.
- `completed`: System1 returned done-result; waiting for/under policy review.
- `approved`: completed output satisfied policies; terminal success.
- `rejected`: completed output failed policy review; must be archived and replaced.
- `canceled`: terminal stop state for that specific task attempt.

## Review Contract
- Review-eligible statuses are `completed` and `blocked`.
- If a `TaskReviewMessage` is received for any other status:
  - System3 sends `InternalErrorMessage` to System5
  - System3 resets task to `pending` and reassigns (best System1 reselected)
  - auto-retry is capped at 3 attempts
  - after cap is reached, System3 keeps escalation-only behavior and does not auto-retry
- `completed` path:
  - all cases `Satisfied` -> `approved`
  - any case `Vague` -> remain `completed` and request clarification/review retry
  - no vague and at least one `Violated` -> `rejected`
- `blocked` path:
  - System3 executes blocked-resolution flow (research/modify/restart)
  - if blocked-resolution determines System1 is not equipped, System3 sends a remediation request to System5
  - result is either resumed execution (`pending` -> reassigned) or `canceled`

## Rejected Task Flow
After a task is `rejected`, handling is always replacement-based:
- original rejected task is moved to `canceled`
- a replacement task is created in the same initiative
- replacement starts as `pending`
- replacement does not inherit assignee; System3 always reselects best System1

Decision split before replacement assignment:
- existing System1 can pass with better information/prompt
- System1 change is required

If System1 change is required:
- System3 compiles structured rejection evidence (cases + execution traces)
- System3 sends remediation request to System5
- System5 may update System1 config/skills or authorize a new System1 profile
- only System5 escalates to user when no viable remediation exists

## Task Attempt Lineage
- Forward link on original task: `tasks.follow_up_task_ids` (JSON list of task IDs)
- Reverse link on replacement task: `tasks.replaces_task_id` (single task ID)
- Expected usage:
  - when a rejected task is replaced, append replacement id to original `follow_up_task_ids`
  - set replacement `replaces_task_id` to original task id
  - keep all attempts as immutable historical records

## Discussion Topics
Use this section to align remaining details before code changes:
- Exact message schemas/payloads for replacement creation and remediation outcomes (see `docs/technical/message_contracts.md`)
- Whether `NX5` should be purely passive wait or publish an explicit heartbeat/monitor event
