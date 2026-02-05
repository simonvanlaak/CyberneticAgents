# External Skills Plan (Clawdbot and Others)

## Goal
Support third-party skill packs (e.g., `@clawdbot/*`) without vendoring them into
`src/tools/skills`, while keeping builds reproducible and low-maintenance.

## Plan

### 1) External Skills Root
- Introduce `CYBERAGENT_SKILLS_EXTERNAL_ROOT` (default `/app/skills` in Docker).
- Update the skill loader to search both:
  - Internal: `src/tools/skills`
  - External: `CYBERAGENT_SKILLS_EXTERNAL_ROOT`

### 2) Pin and Install External Skills
- Add a manifest file (e.g., `config/skills_external.json`) listing skills and versions.
- Example manifest entry:
  - `{ "source": "@clawdbot/notion", "version": "x.y.z" }`
- Use the `skills` CLI to install from the manifest into the external root.

### 3) Docker Build Integration
- In `src/cyberagent/tools/cli_executor/Dockerfile.cli-tools`:
  - Install the `skills` CLI (Node).
  - Run `skills install` per manifest into `/app/skills`.
  - Cache/pin versions for reproducibility.

### 4) Sync Script (Local + CI)
- Add a script (e.g., `scripts/sync_external_skills.sh` or Python) that:
  - Reads the manifest.
  - Installs or updates skills in the external root.
  - Can be run locally and in CI/build steps.

### 5) Keep Internal Skills Stable
- Do not modify existing internal skills.
- External skill updates should be isolated to the manifest + sync step.

## Notes
- This approach supports multiple external sources (clawdbot, others).
- Reproducible builds come from pinned versions in the manifest.
