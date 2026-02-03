# Product Requirements – Production Readiness

## Summary
Define the minimum scope to make CyberneticAgents production‑ready for a single‑team deployment with CLI + Telegram. This PRD focuses on reliability, security, observability, and operational workflows.

## Goals
1. **Reliability**: Runtime starts, stays healthy, and recovers from common failures.
2. **Operational clarity**: Clear logging, status, and diagnostics.
3. **Secure secrets**: No plaintext secrets in logs or files.
4. **Channel robustness**: Telegram delivery is reliable and monitored.
5. **Safe upgrades**: Predictable migrations and backward‑compatible data.

## Non‑Goals (for now)
1. Multi‑tenant / multi‑user shared inboxes.
2. Slack/Email channels.
3. High‑availability clustering.

## Requirements

### Runtime & Lifecycle
- Automatic runtime start after successful onboarding.
- Explicit status command that reports runtime PID and health.
- Graceful shutdown on stop and system signals.
- Restart on crash with clear error logging.

### Observability
- Structured logs with timestamps and severity.
- CLI command should surface new WARNING/ERROR logs since last run.
- Health checks for:
  - Runtime process alive
  - Database connectivity
  - Telegram channel connectivity

### Secrets & Configuration
- Support secrets from environment and 1Password.
- Avoid logging secrets.
- Provide `.env.example` covering required variables.
- Onboarding validates required secrets and offers to store them.

### Data Safety
- Inbox persistence must be backward compatible.
- Migrations are versioned and reversible.
- Corrupted local state should not crash the runtime.

### Telegram Channel (Production)
- **Webhook mode support is required**.
- `TELEGRAM_WEBHOOK_URL` must be configured for production deployments.
- Webhook secret validation is enforced when `TELEGRAM_WEBHOOK_SECRET` is set.
- Clear diagnostics when webhook registration fails.
- Polling remains available for local development only.

### Operational UX
- `cyberagent onboarding` must be idempotent.
- `cyberagent start` and `cyberagent restart` print clear next steps.
- `cyberagent inbox` should display channel warnings (e.g., Telegram disabled).

## Success Metrics
1. Runtime starts successfully on first run.
2. Telegram messages are received and responded to within 5 seconds in webhook mode.
3. No secret values appear in logs.
4. Onboarding completes with clear guidance in under 5 minutes.

## Open Questions
1. What is the minimal health‑check endpoint shape for automation?
2. Do we require a CLI command to test Telegram connectivity?
