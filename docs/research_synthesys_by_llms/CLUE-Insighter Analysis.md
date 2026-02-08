# CLUE-Insighter (LLM-Interviewer) Analysis

Source repository (cloned into `/tmp/LLM-Interviewer`): `insighter/` pipeline from `cxcscmu/LLM-Interviewer`.

This document summarizes what `insighter/` does, what is reusable for CyberneticAgents onboarding, and what would need adaptation.

## Summary
`insighter/` is a batch analysis pipeline that processes chat + interview logs to produce:
1. Quality filtering of sessions.
2. Interaction statistics (rounds, tokens, time).
3. Classification of interview questions into fixed dimensions.
4. LLM-based ratings per dimension + per-record aggregation.
5. Topic modeling over chats + interviews (BERTopic).
6. Plots (topic distributions, correlation heatmaps).

Entry point: `insighter/main.py` orchestrates steps 1–9.

## Pipeline Steps (from code)
1. **Compile conversations**: `get_data.py` merges all `.json` logs into `data/conversations.json`.
2. **Filter logs**: `data_cleanup.py` filters low-quality sessions using heuristics + LLM classifier.
3. **Statistics**: `interaction_statistics.py` computes rounds, token counts, engagement time.
4. **Classify Q/A into dimensions**: `insight_analysis.py` labels each assistant question into RQ1–RQ6.
5. **Ratings per session**: `rating_averages.py` (LLM ratings) + `ratings_per_record.py` (aggregate).
6. **Topic analysis (chat)**: `topic_analysis_chats.py` (BERTopic + OpenAI embeddings + Claude labels).
7. **Topic analysis (interview)**: `topic_analysis_interviews.py` (extract insights, then BERTopic per dimension).
8. **Topic plots**: `topic_plots.py` generates bar plots.
9. **Correlation plots**: `correlation_plots.py` plots Spearman correlations between ratings.

## Reusable Components for Onboarding
### 1) Quality filtering (`data_cleanup.py`)
- **What it does**: flags low-quality sessions based on short length, chatbot-like phrases, emoji-heavy content, and LLM classification.
- **Reuse**: add a quality gate to onboarding interviews before committing to memory.
- **Adaptation**: replace chatbot-specific phrases with onboarding-specific noise patterns (e.g., repeated placeholders, random text).

### 2) Question classification (`insight_analysis.py`, `dimensions.py`)
- **What it does**: labels each Q/A pair into RQ1–RQ6 (understanding, meet need, credibility, satisfaction, improvement, overall feelings).
- **Reuse**: use the same classification method to track onboarding coverage.
- **Adaptation**: redefine dimensions for onboarding discovery (goals, workflows, pains, constraints, success criteria, tools).

### 3) Session stats (`interaction_statistics.py`)
- **What it does**: rounds, tokens, time per session, per model averages.
- **Reuse**: lightweight health metrics for onboarding interviews.

### 4) Topic modeling (`topic_analysis_interviews.py`)
- **What it does**: extract insights, run BERTopic to cluster themes per dimension.
- **Reuse**: optional Phase 2 feature to auto-cluster onboarding themes.
- **Adaptation**: replace RQ-based grouping with onboarding dimensions; decide whether to keep BERTopic + OpenAI embeddings.

## Components Likely Overkill for Phase 1
- **Rating correlations**: useful for research papers but not necessary for onboarding.
- **Multi-trial ratings**: 5 trials per item is expensive; may be replaced with single-pass confidence tagging.

## Suggested Onboarding Dimension Set (Draft)
- D1: Desired outcomes/goals
- D2: Current workflow/process
- D3: Pain points/blockers
- D4: Tools/stack/PKM usage
- D5: Success criteria/metrics
- D6: Constraints/risks

## Minimal “Insighter-lite” Proposal
A leaner version suitable for onboarding:
1. Quality gate (heuristics + LLM classifier).
2. Dimension classification of each Q/A pair.
3. Coverage summary (how many Q/A pairs per dimension).
4. Store dimension summaries into memory for System 4.

## Files of Interest (insighter/)
- `main.py` – pipeline orchestrator.
- `data_cleanup.py` – quality filter + session split.
- `dimensions.py` – fixed RQ dimension list.
- `insight_analysis.py` – question classification + rating pipeline.
- `interaction_statistics.py` – session stats.
- `topic_analysis_interviews.py` – insight extraction + BERTopic.
- `ratings_per_record.py` – aggregation of ratings per session.
- `topic_plots.py`, `correlation_plots.py` – visualization utilities.

## Dependencies
See `insighter/requirements.txt`:
- `bertopic`, `hdbscan`, `umap_learn`, `openai`, `pandas`, `numpy`, `seaborn`, etc.

For CyberneticAgents onboarding, we can initially avoid heavy BERTopic dependencies and reuse only the classification/quality logic.

---
If needed, I can produce a concrete adaptation plan (code + tests) for an onboarding-focused “insighter-lite” module.
