Goal: 
create a flexible structure that allows for easy adding of tool capabilities to all VSM agents
Key Resources:
https://agentskills.io/home
https://www.clawhub.com/

Approach:
As in openclaw identified, the best way to provide tools to agents is via cli not mcp.
There are already a lot of cli tools available so this makes it easy to provide the agents with tools, again openclaw can be used as an inspiration for tools here.
All cli tools will be installed in a docker image. The agents will use the EnvDockerCommandLineCodeExecutor to execute these tools as well as provide credentials automatically via 1password integration. Potentially if the docker image gets to large in filesize, it could be split up into tool groups.
The agentskills spec will be used to provide the agent with information on available skills, as this is an industry wide standard already.

skills:
- web_search via https://github.com/joshsisto/brave-search-cli
- web_fetch via Readability



- [ ] Should we have one docker container for all tools? Or one for each tool?
- [ ] How are the tools loaded for the agents?
- [ ] What should be the hard tool limit for agents to prevent context pollution?
- [ ] How are we managing skill permissions? Should we continue to use casbin rbac for this? -> if so we also need to implement a permission management tool again.
