# Onboarding Implementation Plan (Phase 1)

## Goals
- Implement onboarding SOP execution flow with Obsidian repo sync + profile link research.
- Generate onboarding summary artifacts under `data/onboarding/<timestamp>/summary.md`.
- Run discovery interview through shared inbox + `UserAgent`.
- Output System5 purpose + initial System4 strategy only.
- Load onboarding SOP as the root purpose and root initiative when creating the root team.

## Architecture Overview
- CLI command orchestrates technical onboarding (secrets/config validation) and then triggers
  System3 to execute the onboarding SOP.
- GitHub sync uses `git-readonly-sync` skill (PAT via 1Password).
- Markdown ingestion summarizes `.md` files (limit 1,000 files).
- Profile links are fetched and summarized immediately using web tools.
- Onboarding summary is written to file and injected into System4 interview context.

## Inputs
- Required: `user_name`
- Required: `obsidian_repo_url` (private GitHub repo)
- Required: PAT (1Password, used by `git-readonly-sync`)
- Optional: `profile_links[]` (minimum 1 link if web research is enabled)

## Outputs
- `data/onboarding/<timestamp>/summary.md`
- Updated System5 purpose
- Initial System4 strategy

## Data Flow
1. `cyberagent onboarding` starts.
2. Validate inputs and secrets/config.
3. Root team is created with root purpose + root initiative assigned from onboarding SOP.
4. Trigger System3 to execute the onboarding SOP.
5. `git-readonly-sync` clones/pulls repo to `data/obsidian/<repo-name>`.
6. Ingest up to 1,000 `.md` files and summarize.
7. Fetch + summarize profile links.
8. Write onboarding summary file.
9. Start discovery interview via shared inbox + `UserAgent`.
10. System4 writes purpose + strategy.

## TDD Plan
1. RED: Technical onboarding validates required inputs and secrets/config.
2. RED: Root team creation assigns onboarding SOP as root purpose + root initiative.
3. RED: System3 executes onboarding SOP after validation success.
4. RED: Sync step calls `git-readonly-sync` with PAT env and default branch.
5. RED: Ingest step reads `.md` files and enforces 1,000 file limit.
6. RED: Profile link fetch triggers web tool usage.
7. RED: Summary file is written to `data/onboarding/<timestamp>/summary.md`.
8. RED: Interview routes through shared inbox + `UserAgent`.
9. GREEN: Implement minimal code to pass tests.
10. REFACTOR: Clean structure and add brief comments where logic is non-obvious.

## Open Risks
- Web fetch rate limits for many profile links.
- Large Obsidian repos may still be heavy even within 1,000 files.
- Multi-channel interview flow needs clear session routing.
