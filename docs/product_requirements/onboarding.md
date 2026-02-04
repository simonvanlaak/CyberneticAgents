# Planned Feature – Onboarding & Continuous Purpose Adjustment

## Problem Statement
New deployments of the CyberneticAgents VSM currently require a **manual boot‑strapping** phase:
1. The system is started with no defined purpose. 
2. Operators must manually create the first set of goals, KPIs and policies.
3. After the initial setup, purpose adjustments are still performed ad‑hoc.

This manual onboarding is error‑prone and slows down experiments. We need an **automated onboarding flow** that discovers an initial purpose, sets up the basic VSM configuration, and then **continually refines** that purpose as the system gathers data.

## High‑Level Solution
Create an **Onboarding Service** that runs once at first start and then stays active in the background to **re‑evaluate the system’s purpose** on a regular schedule.

## Dependencies
Depends on docs/features/standard_operating_procedures.md
Depends on docs/product_requirements/cron_triggers.md

### 1. First‑Run Discovery
System 4 gets triggered with a default prompt, that starts the discovery process on the user. This is similar to https://docs.openclaw.ai/reference/templates/BOOTSTRAP. However the key difference is to understand the users needs pro actively. The purpose is to achieve viability and for that the system 4 needs to understand user needs.
Additionally this bootstrap run should be easiy on the user. Many LLM Tools have a long onboarding interaction that is tedious when wanting to try them out.
The best way arround is for the user to provide already documented knowledge on them serves. 
1. the user provides their name and System 4 does a quick web search on the user, trying to learn from public information.
  - Require explicit profile links before any web research (minimum 1 link, no upper limit).
2. the user provides access to documents. Phase 1 supports syncing a private Obsidian vault
   stored in a GitHub repo using the `git-readonly-sync` skill and a PAT via 1Password.
   - Ingest all `.md` files in the repo.
   - Limit ingest to 1,000 markdown files.
   - Use the repo default branch.
   - If sync fails, continue onboarding without PKM data but warn the user.
   - Store synced repos under `data/obsidian/<repo-name>`.
   - Sync cadence: hourly.
3.
From this gained knowledge, then could system 4 start interviewing the user equiped with knowledge it is now able to ask more percise questions.
Here Product Discovery principles need to be applied. The VSM is trying to understand what kind of a product it should be.

### 2. Continuous Purpose Adjustment Loop
Product discovery needs to be countinous. Root system 4 should have a regular trigger (daily)
to review what tasks the VSM has completed, check for changes in the knowledge that is availbale
and compare with existing purposes and strategies. It can ask the user follow up questions or
suggest to innovate and automate tasks that have been repeating.

I want to build an LLM Agent based automatic product discovery that asks questions to its user as well as does web research in order to identify user needs, that could be fulfilled by an LLM Agent. Research best practices on understanding user needs in an interview situation supported with additional research. And ultimately create a framework / flow / guide on how the interview should be structured.


Added research results in docs/research_synthesys/AI-Powered User Discovery: A Framework for B2B Multi-Agent Onboarding.md

## Onboarding Inputs (Phase 1)
- Required: user name.
- Required: private GitHub repo containing Obsidian vault (PAT via 1Password).
- Optional: profile links for web research (minimum 1 link required if web research is enabled).

## Onboarding Outputs (Phase 1)
- Create/update System5 purpose.
- Create initial System4 strategy.
- No System3 projects/tasks created yet.

## Interview Flow
After ingesting the Obsidian repo and profile links, run a full discovery interview.
