# PKM Integrations PRD

## Purpose
Define additional Personal Knowledge Management (PKM) integrations beyond GitHub-hosted
Obsidian vaults for onboarding and continuous purpose adjustment.

## Scope
- Provide a consistent ingestion pipeline for multiple PKM sources.
- Align with onboarding data needs without blocking the onboarding MVP.

## Non-Goals (Phase 1)
- Real-time bi-directional sync.
- Advanced semantic indexing across multiple PKMs.

## Dependencies
Depends on docs/product_requirements/onboarding.md
Depends on docs/product_requirements/communication_channels.md

## Phase 2 Candidates
1. Notion API import (workspace + page selection).
2. Obsidian via local folder ingestion.
3. Google Drive / Docs ingestion (read-only).

## Requirements
1. Read-only access with explicit user consent.
2. Token storage via 1Password and environment variables.
3. Clear per-source rate limits and sync cadence.
4. Ingestion emits a summary report usable by onboarding interview.

## Open Questions
1. Which PKM should be prioritized after GitHub-hosted Obsidian?
2. What is the acceptable sync latency per provider?

## Success Metrics
1. At least one additional PKM source integrated with reliable ingest.
2. Onboarding uses PKM summaries without requiring manual curation.
