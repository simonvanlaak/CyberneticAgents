# Technical Onboarding Feature

## Overview
Technical onboarding ensures the CLI can operate safely before the system creates teams or runs workflows. It validates required permissions and integrations (filesystem, Docker, 1Password, network) and provides clear remediation steps. When requirements are missing, onboarding stops early and explains what to fix.

## Core Capabilities
- **Filesystem checks**: Verify `data/` and `logs/` are writable.
- **Docker readiness**: Validate Docker is installed, the daemon is reachable, and the Docker socket is accessible.
- **Skill tool availability**: Confirm the CLI tools image exists when skills are enabled.
- **Secret availability**: Confirm required secrets can be loaded from 1Password or prompted for storage.
- **Network access**: Verify outbound network access when network-bound skills are enabled.
- **State caching**: Skip repeated checks if the environment state is unchanged.

## Runtime Behavior
- The onboarding command runs technical checks before creating teams.
- If checks pass, a default team is created (when none exists).
- If checks fail, onboarding exits with guidance and no state changes.
- When secrets are missing, the CLI can prompt for the key and store it in 1Password (if write permissions exist).

## Secret Handling
- Secrets are sourced from 1Password, with vault name `CyberneticAgents`.
- Each secret is stored as an item named after the env var (e.g., `BRAVE_API_KEY`) with a `credential` field.
- If the CLI lacks write access, it instructs the user to fix permissions instead of prompting for input.

## Docker Checks
- Docker is required only when Docker-based skills are configured.
- Docker socket access is validated separately to catch common permission errors.
- When `DOCKER_HOST` points to a remote TCP host, socket checks are skipped.

## How to Test
Quick test targets:
- `python3 -m pytest tests/cli/test_onboarding_cli.py -v`

## File Map
- `src/cyberagent/cli/onboarding.py`
- `tests/cli/test_onboarding_cli.py`
