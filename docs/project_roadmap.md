# CyberneticAgents Project Roadmap

## ✅ Basic Implementation of Systems 1 - 5

## ✅ Communication between Systems via Delegation & Escalation

## ✅ Permission Management for Delegation & Escalation

## ✅ Support multiple Viable Systems Model Instance (VSMI)
The initial prototype only included a single VSMI. But a key feature of the Viable Systems Model is its recursion.
For this we implement namespaces. Each VSMI will have its own namespace, which will be used to identify and manage its systems.
Most permissions of a system are limited inside the namespace.

## ✅ System 5 Ability to Create New Systems 1-4
System 5 has the ability to create new systems 1-4 as needed. This ensures that the VSMI can adapt to changing circumstances and maintain its functionality.

## ✅ System Recursion
When in an existing Viable Systems Model Instance (VSMI), is not capable of fulfilling its purpose, it can turn one of its existing Sytem 1s into a recursive VSMI.
VSMI can be assigned very complex big picture purposes, that require to be broken down into smaller, more manageable purposes. For example a business might break down have multiple departments, teams and employees.

## ✅ Self Healing
A VSMI has the ability to self-heal, as long as a system 5 is present and functioning properly. This ensures that the VSMI can recover from any unexpected issues or failures. And also is a key part in System Recursion.
System 5 can do a health check on the VSMI and detect if all required systems 1-4 are present.
If any of these systems is missing, it uses the ability to create new ones to replace them.

## Visualization VSMI Overview
There is the need to observe the whole VSMI. This includes what systems are running in it, what child VSMIs are running in it, and what budget is available for each system and child VSMI.
A live view of communication between systems and child VSMIs would also be great.
There are already UIs available for this purpose, they should be utilized as much as possible.
Requirements are:
- Allows for analization of context & prompts
- Allows for cost monitoring of llm & api calls.
- Allows for visualization of message flow and network of agents & tools

I have already tried: Jaeger UI, Langfuse, Langsmith, Traceloop.
Still look at: https://arize.com/docs/phoenix

## Tool Access
In order for the System to successfully execute tasks it needs access to tools that can help it achieve its goals. These tools can be physical or digital, and can include things like sensors, actuators, and software applications.
Currently the best practice in giving LLM-based Agents access to tools is the Model Context Protocol (MCP).
There are already many tools available that can be used with LLM-based Agents.
Providing a simple way for Agents to access these tools is crucial for their success.
Autogen & its extensions also have built-in tool access capabilities, which would be relatively low effort to integrate.
https://smithery.ai/ provides a simple way to access tools.

## Tool Permission Management
An agent with too many available tools to use is looses its ability to choose the proper tools to use.
To prevent this, we need a permission management system that allows agents to request access to specific tools and limits their access to only those tools that are necessary for their tasks.
System 5 is responsible for managing agents permissions in their VSMI as well as child VSMIs.
A System 5 has only the ability to assign permissions to tools that are available to the VSMI.
System 4 has the ability to identify potential tools outside of the VSMI. Equiped with this ability, System 5 can request access to additional tools from its parent VSMI.

## Key Tools
I have identified a few key tools that are essential for the success of the project. These tools include:
### System 1
- Web Search
### System 3
- Project & Task Management / Storage

## System Specific LLM Choice
Different tasks require different levels of intelligence and capabilities. These different levels can be achieved by using different LLMs. However each LLM has its own strengths and weaknesses. And especially different costs.
To ensure that Systems are using the most appropriate LLM for their purpose, System 5 can choose the LLM they use.

## Context Engineering
1. There should be a shared memory for the namespace.
2. We need both short term and long term memory. Short term memory should be a cache that is cleared after a certain amount of time. Long term memory should be a database that is persisted.
3. For longterm memory we need to have CRUD operations.
4. Research what memory features autogen already provides.

## Resource Management (Token Usage)
### Measuring Costs
LLM calls require resources. This project implements LLM API providers, who charge by the input & output tokens used.
Each LLM has its own prices.
Autogen already provides great ways of tracking token usage.
By combining token usage & LLM pricing, we have the capability to calculate the cost of each LLM call.
Costs need to be measured on both System & VSMI level.
Where the cost of a VSMI is the sum of the costs of all its child VSMIs & Systems.
Additionally tool usage can also cause costs. This is the case for example for remote mcps / api usage. This also needs to be considered when calculating the cost of a VSMI.
### Budgeting
Each VSMI has a budget that it can spend on LLM calls.
This budget is strictly enforced by the CyberneticAgents implementation.
However, System 3 can manage how the available budget in a VSMI is distributed among its child VSMIs & Systems.
While the Human operator can set the budget for the root VSMI.
To make an informed decision about the budget allocation, System 3 can see how much budget is still available in its own VSMI, for each system & child VSMIs. What budget is allocated and by how much it recently change & when it is expected to run out (especially if it is expected to run out before the next budget allocation).
Budget allocation is happening in a fixed time interval (this could initially be daily).
For the hard enforcing of budgets we need to predicts the cost of a LLM call or tool use and prevents it if it would exceed the budget.


## Human-in-the-Loop (HITL)
Human in the loop visualization includes a chat message portal. This is intially provided via CLI. How ever in order to improve user experience, this should be provided via a web interface. LibreChat could be a good candidate for this.

## Triggers
### Human-in-the-Loop
### Pulse
### External Triggers (f.ex. E-Mail)

## Enhanced Decision Frameworks
