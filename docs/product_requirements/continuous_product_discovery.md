# Planned Feature – Continuous Product Discovery & Purpose Adjustment

## Goal
Define post-onboarding behavior for continuous discovery on the user and continuous adjustment of purpose/strategy.

## Scope
- Continuous product discovery interviews and follow-up questioning.
- Continuous purpose/strategy adjustment informed by new evidence.
- Background research and ingestion updates after onboarding is complete.

## Out of Scope
- First-run onboarding bootstrap flow.
- Technical onboarding checks and initial team bootstrapping.

## Dependencies
Depends on docs/product_requirements/onboarding.md  
Depends on docs/features/standard_operating_procedures.md  
Depends on docs/product_requirements/cron_triggers.md

## Continuous Purpose Adjustment Loop
- Root System4 runs a recurring review trigger (daily by default).
- Each run reviews completed tasks, new memory, and current purpose/strategy alignment.
- System4 may:
  - propose purpose updates,
  - propose strategy adjustments,
  - ask follow-up user questions when confidence is low.

## Continuous Product Discovery on the User
- Discovery continues after onboarding as an always-on interview/research loop.
- The agent asks focused follow-up questions to deepen understanding of needs, pains, and constraints.
- New user responses and synthesized findings are persisted to memory for future runs.

## Background Research and Sync Cadence
- Profile-link refresh cadence: hourly.
- PKM refresh cadence: hourly.
- New background findings are appended to memory incrementally and become available before subsequent interview turns.
- Named-entity mention heuristic (company, city, product, industry) triggers background web research when entity context is missing in memory.

## Reuse Existing Research (Preferred)
We should reuse validated interview frameworks instead of inventing a new one.

### 1. Anthropic Interviewer
Reference: https://www.anthropic.com/news/anthropic-interviewer

Reusable findings:
- Long-form autonomous interviewing is feasible.
- Separate interview and analysis stages improve reliability.

### 2. CLUE-Interviewer
Reference: https://aclanthology.org/2025.findings-acl.714/

Reusable findings:
- Follow-up probing depth materially improves insight quality.
- Topic coverage can be measured and evaluated.

### 3. Greylock AI-Native User Research
Reference: https://greylock.com/greymatter/ai-user-research/

Reusable findings:
- Discovery cadence can be significantly increased.
- Interview artifacts should be queryable for ongoing product decisions.

## Research Inputs
- docs/research_synthesys/AI-Powered User Discovery: A Framework for B2B Multi-Agent Onboarding.md
- docs/research_synthesys_by_llms/LLM Agents for Autonomous Interviews: State of Research and Development Introduction.md
- docs/research_synthesys_by_llms/CLUE-Insighter Analysis.md

## Acceptance Criteria
1. A daily System4 trigger executes continuous purpose review and stores a review artifact.
2. Hourly profile-link refresh runs and stores new/changed findings in memory.
3. Hourly PKM refresh runs and stores new/changed findings in memory.
4. Follow-up discovery questions can be triggered after onboarding without rerunning onboarding.
5. Purpose/strategy change proposals include evidence references from recent memory.
