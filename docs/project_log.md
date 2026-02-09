# CyberneticAgents Project Log

## 2026-01
### 2026-01-06
Project initialization with foundational commits. Implemented multi-agent System 1 pools with composite IDs. Created BaseSystem abstract class and chat history persistence. Added architectural analysis comparing BaseSystem vs agent.py approaches and fixed initial VSM prototype tool calling issues.

### 2026-01-07
Built comprehensive tool permission infrastructure with per-tool permission tables and declarations. Implemented proper VSM hierarchy permissions with System 3 as entry point. Fixed delegation, escalation, and communication flows. Added database initialization and lazy loading capabilities. Improved error handling and tool naming conventions throughout the system.

### 2026-01-08
Fixed session isolation by changing session_id to Integer type. Added comprehensive documentation including CLAUDE.md guidance. Implemented echo-specific System 1 configuration with math tools. Added model configuration system with optimized assignments per system. Fixed various bugs including infinite recursion and TypeErrors. Enhanced testing with model queries and token limit verification.

### 2026-01-09
Conducted major codebase refactoring to improve architecture and prepare for new features. This laid the groundwork for subsequent RBAC and AutoGen integration work.

### 2026-01-10
Integrated RBAC using Casbin for comprehensive access control. Implemented AutoGen Core Runtime as the foundation. Updated RBAC model to support role-based access control and added proper gitignore configuration for build artifacts.

### 2026-01-11
Implemented the delegate tool using AutoGen framework and performed significant code refactoring. Fixed various implementation issues to stabilize the core functionality and prepare for production use.

### 2026-01-12
Resolved critical issues including JSON serialization errors with AgentId types and permission resetting bugs. Fixed delegate/escalate functionality and user messaging. Added command line support for non-interactive mode. Improved RBAC policies with simplified role structures and better message handling with visual separators.

### 2026-01-13
Major namespace implementation milestone with comprehensive system evolution capabilities. Fixed circular imports and RBAC policy enforcement. Implemented cross-namespace routing logic and automatic permissions. Added extensive testing framework and updated documentation. Achieved recursive VSM iteration where System 1 can evolve into complete VSM structures.

### 2026-01-14
Refactored tools to use the new RBAC base class architecture. Fixed runtime initialization issues and agent registration problems. Enhanced logging and code formatting in main.py and agent-related code for better maintainability.

### 2026-01-15
Finalized LLM provider integration planning and code quality improvements. Fixed return types across multiple tools to use FunctionExecutionResult consistently. Updated exports in tools __init__.py and removed unused imports. Added SystemEvolve documentation to policy prompts and improved code formatting throughout the codebase.

### 2026-01-16
System evolution is now implemented. There are still some minor issues, when the newly created System 5 receives its first request it does not perform a heath check and creates new systems, but instead responds to the request itself. I think the main weakness of the system currently is the agents decision making. Here I think I either need to
1. improve ther systems prompt through experimentation
2. create specified messages for Delegate, Escalate etc and then use different system prompts depending on the message the agent received, reducing the possible decisions than need to make and simplyfing it
3. Implement strict decision making logic, where during the handling of one request the agent goes through a predefined logic to make a decision. This would require addition llm calls through, for each step in the hardcoded logic.
Now I'm working on implementing observability. I have already implemented local Jaeger Ui, as well as cloud langsmith, but at this point both don't provide me with the visualization I'm looking for. This would be in best case a live view of how messages flow though the different agents & tools, or a graph visualization after the fact, showing the network of agents & tools that were involved in the trace.
Langsmith did provide a very important visualization, which was showing the prompt that gets sent to the llm. This allows for context engineering. As well as costs.
I also tried out langfuse & traceloop.
So far Arize was the best at creating a graph. But I'm noticing its not 100% accurate, and the website is loading slowly.
I think it would be easier to write a little script that turns the casbin policies into a mermaid chart.
This way it's 100% accurate, it could be live and we could also easily visualize all the communications that are allowed.

### 2026-01-18
I spent some time implementing my own real time observability, but it prooved to be much more difficult than expected. This made me rethink why I wanted real time observability and actually that was more to "play arround" and experiment. But in a later scenario I probably want to run a bunch of different simulation possibly at the same time and be able to review them later on.
So I will now go back and revisit the tracing options I looked at.
Langfuse is my favorite here, because it was easy to set up, had good visualization and is open source.

While langfuse is working. The traces are sparate between each "send_message" function call of the runtime. But the goal is to have a single trace across multiple agent handoffs.

### 2026-01-19 - 2026-01-21
Working on continuing the trace across multiple agent handoffs.

### 2026-01-22
I reviewed the whole project, especially thinking about how this hypothesis of "VSM can be used to structure MAS", can be validated.
For that I have looked into MAS Benchmarking. For that I have found the article "Will Fu-Hinthorn. (2025, June 11). Benchmarking Multi-Agent Architectures. LangChain Blog. https://www.blog.langchain.com/benchmarking-multi-agent-architectures/" which described how LangChain has benchmarked different MAS architectures. Using an expansion on T-Bench (Yao, S., Shinn, N., Razavi, P., & Narasimhan, K. (2024). $τ$-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains (No. arXiv:2406.12045). arXiv. https://doi.org/10.48550/arXiv.2406.12045).
They use this in order to compare different MAS architectures, such as Swarm, Supervisor, and others and copared those to single agents.
I looked into using this to evaluate the VSM, but their code is written to test langchain while I am using AutoGen to implement the VSM, meaning it would be significant effort to adapt their code to my needs.

### 2026-01-23
I further reiterated on this project thinking, that I have found a solution without a problem. I need to find out exactly what I could use CyberneticAgents for. What could they be used for?
The VSM is used to mainly organize businesses. So the CyberneticAgents would need to be a business in order for this to make sense.
The business I want to create is a Software/Product Consultant Business. So my idea is that the CyberneticAgents could be consultants.
I have two great sources for Product Management & Entreprenourschip those are:
1. Michael Skok. (n.d.). Startup Secrets Sandbox. Coda. Retrieved October 14, 2024, from https://coda.io/d/Startup-Secrets-Sandbox_dqDyOX97fb9/Welcome-to-the-Startup-Secrets-Sandbox_suAzHnI0#_luVWJHjr
2. ChatPRD/lennys-podcast-transcripts. (2026). [Shell]. ChatPRD. https://github.com/ChatPRD/lennys-podcast-transcripts (Original work published 2026)
If the CyberneticAgents (CA) should act as a business one of the key features I have not defined yet, is strategy and planning.
The idea is that big tasks need to be broken down into smaller tasks and assigned to the right system 1 experts, additionally system 1 experts need to be defined based on overall purspose, for this it needs to be research what roles / jobs to be done typically exist in that domain. Both of these tasks could be handled by system 4?
If I want to focus on this business / consultant approach. The first question to ask the user is "What is your business?" and define that as a purpose/domain for system 5.
But then what should the CyberneticAgents do? I think the initial steps need to be clearly pre defined until one can just have the system be on its own. I think this is a critical step to agentic systems, how much agency can they get?
Maybe this can be then broken down into the next questions to ask the user: at what stage is your business current? Still in discovery, already has customers etc? Maybe for this I could find some basic consultant resources, basically the system needs to quickly understand and what stage the business is.
Alternatively this could just be focused on product discovery, and CA starts "from scratch" trying to discover a product.
For product discovery, the provided resources could already be turned into a simple playbook/strategy.
Maybe a strategy could be an entity / structured object and product discovery could be a pre-defined strategy. That can be instantly applied, while system 4 can also create new strategies as well as adapt existing ones.

I have expanded the feature_breakdown.md file, this now also includes the strategy component of sys4 and project management component of sys3.

### 2026-01-26
I have broken down some features even more.
We now have:
One VSM Instance has one purpose defined by System 5.
To achieve this purpose, multiple strategies are defined by System 4.
To execute a strategy, system 4 defines projects.
Projects are split up into tasks by system 3.
System 3 delegates tasks to be executed to multiple system 1s.

And I also started to define the message structures than get exchanged between the systems.
I also have splin up the general vsm agent into multiple smaller ones (one for each system type).
The next step is to implement detailed context and decision making logic for each of the received messages.
Limiting what context is provided, and what tools are available guarantees percise decision making.

### 2026-01-28
I have now implemented the different agents for each system and included some hardcoded decision frameworks as well as some minimal context engineering.
I have also implemented the Task breakdown structure in the sqllite database and its usage.
There are still a few functions not implemented, those raise a NotImplementedError, to ensure this does not get missed.
Additionally, there are still bugs in the code. The most current one being: openai.BadRequestError: Error code: 400 - {'error': {'message': 'json mode cannot be combined with tool/function calling', 'type': 'invalid_request_error', 'param': 'response_format'}}
I will continue to bug fix this until I move on with next implementations.

### 2026-01-29
Message sending now work between UserAgent & System4.
Next I need to develop a test that involves all the different systems.
Also need to implement tools (like webbrowser)."I need product discovery research that evaluates how the technology of Multi Agent Systems could be turned into a product and what potential customers exist there."

### 2026-01-30
I have a problem with communicating with the system asyncronousely. System 4 is great at asking questions and also creates the strategy effectively. But then it asks the user if there is anything else to do. Even if the user respons with no, system4 still continues requseting information from the user. Only when the programm gets exited is the loop free for the other systems to do their work.
The problem is that while messages are being sent async, the user input is not async so whenever user input is requested it blocks the whole thread.
I think this is mainly due to the limitation of the current TUI that I'm using. The solution might be creating a TUI that can receive & send messages between user & angent asyncronously.

### 2026-01-31
Added CLI initial message support and headless mode for faster testing. Split user-contact into two tools (inform vs ask) and improved metadata handling so user updates and questions are correctly routed to the UI. Implemented persistent per-run chat logs under `logs/` and filtered out internal debug lines. Improved TUI presentation: "Latest update” panel, and combined updates/questions in the same area. Fixed System4 strategy creation flow and database persistence issues by adding missing `add()` methods, default purpose creation, and safe DB flush/commit. Added fallback assignment to System3 when initiative selection fails to ensure execution proceeds. Added targeted tests across UI state, tools, System4 strategy flow, and model persistence.

Initial open-source posting of the project repository.
To prevent a lot of back and forth when testing I changed the initial test prompt to "I need product discovery research that evaluates how the technology of Multi Agent Systems could be turned into a product and what potential customers exist there. I don't have a specific industry in mind yet. I have 1 month time and a budget of 200 Euros. I have a working technical prototype. Don't ask me more questions, but start creating & implementing a strategy.".

Disable TUI again, in order to go back to cli. The big benefit of going cli first as interaction, is that coding agents can easily test it and interact with the system. This way development with coding agents should be more effective.
Implemented tools start,stop,status,suggest,inbox,watch,logs,config,login,help and serve

Next step is to make sure test coverage reaches 70% (not far off) and then restructure the projects code architecture as outlined in the plan in the docs. This ensures we are moving forward with a clean project.

## 2026-02
### 2026-02-01
I continued thinking about this project and came to the conclusion that a key aspect is ensuring viablitiy of the system.
Viability in this context, is that the user keeps using the CyberneticAgents (CAs) and feels like that the value created is grater than the cost.
With token cost being relatively high, a key objective of the CAs needs to be to ensure that it understand what brings value to the user.
This is the default / hard coded purpose of the root team. And it needs to continuesly identify the users problems / needs in order to formulate strategies in creating value. While at the same time monitoring the costs.
Onboarding is a critical step here, I noticed that I stopped using most of the LLM tools in the first day, because I'm tired of onboarding and setup. 
Especially open source tools need a lot of setup, because you need to bring your own key etc. So I decided to change the focus of the project on clean onboarding for now.
I thought the best way for the user to onboard the CAs is to give them access to a lot of information that is already written down, then the agents can analyze that to get a quick understanding of the user nedes without requiring a lot of user input.
The best way to get access to that information is to 1. research the user online and 2. get access to a Personal Knowledge Management (PKM) tool (like Obsidian or Notion).
Thus the next focus is to, give the agents access to the Web and PKMs.
The approach to tooling should be a very easily expandible one, which can easily utilize existing tools.
The openclaw ecosystem is great for this because it provides a lot of agent friendly tools already and is a fast growing community.
The next step then is to have openclaw tools / skills work with CAs.

However, tools require secrets. Most tools require some kind of API KEY and I want to make sure that we don't run into any security issues here. So I want to start with a clean secret management.
I have implemented such a secret management via 1password cli and having all tools run in docker containers.
The running of tools in docker containers also ensures some sandboxing and prevents the agents from breaking themselves accidentally.
However the docker image for this container isn't completed yet. I have planned this in more detail in docs/product_requirements/agent_skills.md

I have written & posted the first blog post today, also in this project at docs/blog-posts/2026-02-01 introducing cybernetic agents.md
I have reached out to people who have posted online about similar ideas on using the VSM for multi agent systems and have asked them for feedback on my project as well as if they are interested to collaborate on this.

I have removed the old tools that we don't need anymore.
I have fixed the failing tests.
I have ran a full refactor on the project to ensure architecture stays clean.

The next step is to implement the docs/product_requirements/agent_skills.md plan and enable web search & web fetch capabilities.

### 2026-02-02
I completed the refactoring and pushed.
Implemented:
  - docs/features/standard_operating_procedures.md
  - docs/features/technical_onboarding.md
  - docs/features/speech_to_text.md
  - docs/features/secret_management.md
  - docs/features/agent_cli.md
  - docs/features/skill_permissions.md
  - docs/features/agent_skills.md

I have further polished my working style with codex. First I discuss product ideas I have with codex and create a PRD in docs/product_requirements then I let an agent implement them. Once their implementation is verified, the PRD gets deleted and a feature entry like the ones above gets created. 
I still haven't manually tested most of these though. I need to integrate this in the flow the next times.
After manual testing I also need to do another architecture & docs review, to ensure that we are keeping everything clean. A lot of features were added, so a change of architecture might be required.

### 2026-02-03
Updated shared inbox behavior and documentation. Unified shared inbox entries across CLI and inbox channel, and enforced routing warnings with related test coverage. Refined telegram integration docs with updated verification steps and setup guidance.
Manually tested telegram feature.

### 2026-02-04
Implemented memory. Created config dir with default team & procedures defined. Created onboarding procedure. Continued working on onboarding experience, including technical check, feature activation check and providing basic user infos to prepare onboarding interview. Implemented reset command, to test onboarding more easily.
Test command: cyberagent onboarding --name Simon --repo https://github.com/simonvanlaak/maya-obsidian-vault --profile-link simonvanlaak.de
Wrote down plan to have agents to research in the background in web and on the provided personal knowledge management (PKM) -> which is a private github repo with .md files for now from my obsidian vault.
The user interview is happening while the CyberneticAgents are getting setup and research is happening. The interview is being enriched by the research results in the background, by writing research results into global memory. 
Cleaned up onboarding more, and integrated telegram messaging in onborading experience. Issue now is that telegram voice not could not be
transcribed.

### 2026-02-05
Completed memory implementation, still needs to be manually tested. Fixed & manually verified telegram messaging and that STT works via telegram voice notes.
Implemented Notion as Agent Skill, but still needs to be integrated into onboarding.
Implemented message-routing agent skill that allows for the directing of user messages from different channels to specific systems.
I changed the telegram onboarding to include setting up the telegram bot with the telegram botfather.
I need to manually go through the onboarding again, now I got a lot of duplicate telegram messages.

### 2026-02-09
I wrote another blog post, this time about onboarding.
I created a minimal kanban dashboard to review the current tasks, strategies, and their status.
Debuged a lot of little issues, to ensure tasks get executed as expected.
Swithed provider & model to openai and gpt-5 nano, to prevent issues with structured output.
