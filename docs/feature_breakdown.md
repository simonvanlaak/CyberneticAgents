## Unassigned features / open questions
### Resource Management / Limiting of token usage.
A critical part of the VSM is the profit/loss analysis of system 1s. But in agents the only information close to this is the token usage. How could we effecticly implement this?

## Structures (Of Tasks / Plans not sure how to name this)
Purpose -> Strategy -> Project -> Task

One VSM Instance has one purpose defined by System 5.
To achieve this purpose, multiple strategies are defined by System 4.
To execute a strategy, system 4 defines projects.
Projects are split up into tasks by system 3.
System 3 delegates tasks to be executed to multiple system 1s.



## System 1 Operations
System 1 is the executor of tasks. Each system 1 has a specific purpose and expertise.
### Configuration
1. Large Language Model used
2. System Prompt (There should be a very strict limit on how long a system prompt can be)
	1. Identity of the System 1 (containing the role, purpose and fields of expertise)
	2. Values & Ethics
	3. Boundaries
	4. Domain specific facts
	5. Interaction Style
	6. Specific Edge-cases
	7. When to escalate to system 3
	8. Version Control (when system prompt was last changed)
	9. Response structure
	10. Available Tools for use and their description
3. Tools
	1. Escalation to System 3
	2. Collaboration with other System 1s
	3. Other Tools and what actions can be performed with them.
	4. Search Knowledge database. Automatically filtered by clusters that sys1 has permission to read, if none don't show tool.

### 1.1 Task Execution
Trigger: Receives a task from sys3.1

Context:
1. Existing system prompt
2. Optionally: references to similar completed tasks that can be searched
3. Task content

Action:
1. Evaluate if capabilities exist for task to be completed (missing tools)
	1. Escalate to System 3.2 inability to complete task. Contains reason on why task can not be completed
2. Execute Task
3. Send Task Completion Report to Sys 3* for evaluation (TaskResultMessage)

## System 2 Coordination
### 2.1 A2A agent-to-agent communication
- [ ] Already implemented via Autogen
### 2.2 Knowledge Database
- [ ] TODO
### 2.3 Oszillation Detection
- [ ] TODO: how can system2 detect oszillation without high resource usage? It could run a quick audit every 10 messages sent A2A for example.

### 2.4 Project Management
I think implementing a full project management system (like jira, plane, github projects etc.) could be a bit overkill though and might be to much of an investment.
The simplest solution wins here and that would be either https://github.com/bsmi021/mcp-task-manager-server or just having an .md file with write read access.
Since sys3 is delegating tasks anyways, there is no need for the sys1 to have access to the tasks.
I think in the future it is critical though that the user can have a live overview on the project & task progress.

The structure of this could be following https://www.projectmanagement.com/deliverables/538317/project-charter-template
or whatever mcp-task-manager-server defines -> at this point just a name.

### 2.5 Strategy / OKRs (Objectives & Key Results)
A strategy is a big picture plan to achieve the VSMIs purpose. And is proken down into multiple projects which are managed by the 2.4.
This could be simply stored as a .md file via the langchain file system tool https://docs.langchain.com/oss/python/integrations/tools/filesystem and the autogen langchain tool wrapper https://microsoft.github.io/autogen/stable/reference/python/autogen_ext.tools.langchain.html#module-autogen_ext.tools.langchain

## System 3 Control
### 3.1 Task Delegation
Trigger: System 3 receives a task (either from a user, different VSMI or an external trigger such as an E-Mail being received) -> AssignTaskMessage
Context:

1. List of all existing system 1s and their roles / capablities / descriptions
2. History of completed tasks that can be searched for reference

Action:
- [ ] How can be decided if a task should be broken down into multiple sub tasks? should this maybe be handled by a system 1? Or does this automatically happen inside the system one in the sub-VSMI?
1. Evaluates if the task matches any of the existing sys 1s roles & capabilities
2. If a sys 1 was found that could handle this task, delegates the task using AssignTaskMessage
	1. Optionally pass similar tasks that have been found.
3. If no sys 1 was found that could handle this task, escalates the task to sys 5.3 -> CapabilityGapMessage

### 3.2 Sys1 Incapable of handling Task
Trigger: Sys1 evaluated that a received task can not be completed with existing capabilities and tools (basically 3.1 made a mistake in delegating this task) -> CapabilityGapMessage
Context:
1. Task
2. Reason of sys 1 for not being able to handle task

Action:
This can basically be redirected to 3.1 just with the enhanced context of the sys1 reasoning. The following actions should be the same as in 3.1

### 3.3 Successful Task Followup
Trigger: Sys3* evaluated task completion as not in violation -> TaskResultApprovedMessage
- [ ] TODO
Action:
1. Forward to task requestor
ForwardTaskResultMessage: {
  "result": "Approved",
}
2. Look into the project management tool, in order to find a new task that should be delegated to the sys1 that is now available.

read_open_tasks_tool: {
  "project_id": 123,
} -> {
  "tasks": [
    {
      "id": 456,
      "content": "Update project documentation",
    },
    {
      "id": 789,
      "content": "Review project budget",
    }
  ]
}

### 3.4 Project Management
Trigger: Receives a project definition from system 4.2
-> breaking down of a big task into multiple small tasks, defining dependencies, assigning multiple tasks to sys1s (using 3.1), triggering the execution of tasks.

create_tasks_tool: {
  "project_id": 123,
  "tasks": [
    {
      "content": "Update project documentation",
    },
    {
      "content": "Review project budget",
    }
  ]
}
assign_task_tool: {
  "task_id": 456,
  "assignee": "sys1"
}


### 3* EvaluationSystem (Judiciary)
https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
Trigger: A System 1 Completes a Task

Context: A packet of Task & System 1 actions (including response and tool calls). Searches ruling database to find a similar case to enrich context.
Model: groq openai/gpt-oss-safeguard-20b
Action:
Evaluates and scores system 1s execution of the task, based on a set of policies. As either in violation or not.
Maybe we need to loop over each policy? That would be a lot of llm calls though.
1. Reviews task solution based on policies with either (violated, not violated, policy vague)
	1. If ruling is "not violated" no intervention
		1. Forward completed task package to sys3.3
	2. If ruling is "violated"
		1. Collect context for the case (task & solution)
		2. how the policy was interpreted and how this applies to this case
		3. exactly what law was violated
		4. Forwards ruling to 5.1 agent correction systems
	3. If ruling is "policy vague"
		1. Collect context for the case
		2. Identify vague policies
		3. Exactly describe how policy could be interpreted in multiple ways
		4. ask questions for clarification
		5. forward ruling to 5.2
2. creates an entry in a database that can be referenced in future rulings
3. Identifies if interaction contained any new information that could be a relevant policy. For example the user could write something like "always answer in less than 3 sentences" this needs to be clearly identified as a policy. If there are these policy suggestions identified, it needs to escalate to 5.5.


## System 4 Intelligence
### 4.1 Knowledge Clustering
Trigger: New document is added to the knowledge base.
Context: Existing knowledge clusters
Action:
1. Sys4 analyzes the content of the new document
	1. creates a short summary
	2. creates connections with existing documents
2. Evaluates if document matches none/one/multiple custers
	1. If document does not match any existing clusters,
		1. a new cluster is being created
		2. System 5.4 is being informed on the new cluster
		3. Existing knowledge base is being searched to evaluate if other documents fit that new cluster (and they get added to the cluster)
	2. If the document does match, it gets added to the cluster(s)

### 4.2 Strategy
Trigger: from system 5


Context: Vague Problem / Purpose Description
Goal: Breakes down a bigger / vague problems into a consise strategy and defines projects inside this strategy.
Action:
1. Researches internal knowledge to get more context on the vague problem
2. Researches external knoweldge sources (like web) in order to find best practices in creating a strategy for the problem.
3. Defines an over all strategy
4. Defines projects inside the strategy
5. Researches what roles are needed in the projects and defines roles.
  1. Negotiates with System 5.5 for needed roles
6. Creates first project definition including goals and roles.
7. Assignes first project to system 3.4

create_strategy_tool: {
  "strategy_name": "Strategy Name",
  "strategy_description": "Strategy Description",
  "projects": [
    {
      "id": "p12345",
      "name": "Project Name",
      "description": "Project Description",
      "goals": ["Goal 1", "Goal 2"],
      "status": "pending"
    }
  ]
}
start_project_tool: {
  "project_id": "p12345",
}

### 4.3 Project Review / Strategy Adjustment
Trigger: System 3.4 has declared a project as completed

Actions:
1. Review the success of the project
2. Review gained knowledge.
3. Adjust strategy accordingly.
4. Assign next project to system 3.4

read_strategy_tool: {
"strategy_id": "s12345",
} -> {
  "strategy": {
    "id": "s12345",
    "name": "Strategy Name",
    "description": "Strategy Description",
    "projects": [
      {
        "id": "p12345",
        "name": "Project Name",
        "description": "Project Description",
        "goals": ["Goal 1", "Goal 2"],
        "status": "completed"
      }
    ]
  }
}

## System 5 Policy
Definition of purpose of the whole VSMI.
Definition of policies that apply to all system 1s.

### 5.1 Agent Correction System
Trigger: 3* rules a system 1 is in violation of a law.

PolicyViolationMessage

Context: Receives a ruling from 3* Evaluating System
Action:
1. Reviews the ruling and modifies the configuration of the system 1 in violation.
2. Evaluates if task might be to complex to be handled by one system1 and if it could be broken down into multipel subtasks, if that is the case, trigger the recursion of that system 1 via 5.6. One clear rule for triggering the recursion is that sys1 has access to a lot of tools, a very long system prompt, has a low task completion rate, or knowledge this needs to be limited.
3. Reinrassiges the task that was violated, to verify that agent config changes ensure that same task will now be fulfilled without any violations. Including a reasoning why none of the sys1 can handle this task.

create_policy_tool: {
  "system_id": 123,
  "policy": {
    "name": "New Policy",
    "rule": "Description of the new policy",
  }
}
update_system_permissions_tool: {
  "system_id": 123,
  "permission": {
    "file_system_tool": "read"
  }
}
system_recursion_tool: {
  "system_id": 123,
  "recursion_purpose": "To handle complex tasks by breaking them down into smaller subtasks."
}

### 5. 2 Policy Clarification System
Policies are certain laws that system 1s are enforced to follow. They define how system 1s need to operate.

Trigger: 3* has judged policies as vague on task completion evaluation -> PolicyClearificationRequest
Context: Receives ruling from 3* Evaluating System

Action:
1. Evaluates case and existing policies
2. Either replaces vague policy and potentially adds more policies in order to provide clarification
3. Responds to 3* Evaluating System with new policies and triggers new evaluation.

create_team_policy_tool: {
  "policy": {
    "name": "New Policy",
    "rule": "Description of the new policy",
  }
} -> {
  "policy_id": 789,
}
create_system_policy_tool: {
  "system_id": 123,
  "policy": {
    "name": "New Policy",
    "rule": "Description of the new policy",
  }
} -> {
  "policy_id": 789,
}
read_system_policies_tool: {
  "system_id": 123,
} -> {
  "team_policies": [
    {
      "id": 1,
      "name": "Policy Name",
      "rule": "Policy Rule",
    },
    {
      "id": 2,
      "name": "Another Policy",
      "rule": "Another Policy Rule",
    },
  ],
  "system_123_policies": [
    {
      "id": 1,
      "name": "Policy Name",
      "rule": "Policy Rule",
    },
    {
      "id": 2,
      "name": "Another Policy",
      "rule": "Another Policy Rule",
    },
  ]
}
delete_policy_tool: {
  "policy_id": 456
}

### 5.3 Agent Creation System
Trigger: System 3.1 has received a task that can not be handled by any of the existing sys 1s. -> CapabilityGapMessage
Context:
1. The task that can not be handled
2. List of existing sys 1s
3. Reasoning of sys 3.1 on why the task can't be handled.
4. Best practices in system 1 configurations

read_systems_tool: {}->{
  "systems": [
    {
      "id": 123,
      "name": "System Name",
      "description": "System Description",
      "permissions": [
        "file_system_tool": "read",
      ]
    },
    {
      "id": 456,
      "name": "Another System",
      "description": "Another System Description",
      "permissions": [
        "file_system_tool": "read",
      ]
    },
  ]
}



Action:
1. Defines a new system 1 configuration
2. Creates basic evaluation policies for new system 1 configuration (there should be a default that can just be applied)
3. Delegates task to new system 1 configuration (which will respond to system 3.1 NOT system 5)

create_system_tool: {
  "name": "New System",
  "description": "New System Description",
  "permissions": [
    "file_system_tool": "write",
  ],
  "policies": [
    {
      "name": "New Policy",
      "rule": "New Policy Rule",
    },
  ]
} -> {
  "system_id": 789,
  "policies": [123]
}

### 5.4 New Knowledge Cluster
Trigger: System 4.1 created a new knowledge cluster
Context:
- All existing sys1s, their roles and what knowledge clusters they currently have access to.
- Name & description of the new knowledge cluster
Action:
1. Evaluates if any of the existing sys1s should get access to the new knowledge cluster and if the case, assigns them the new cluster.

### 5.5 Policy Suggestion Evaluation
Trigger: Sys3 or Sys4 have identified something that could be a new policy
- [ ] TODO

### 5.6 Recursion
Expand an existing sys1 into a new recursion of the VSM. This creates a default sys 1,3 & 5. Where the purpose of the whole VSMI is the purpose of the replaced sys1.

### 5.7 Request a strategy

RequestStrategyMessage: {
  "content": "Create a strategy for the project"
}

```mermaid
graph:
 a-->b

```
