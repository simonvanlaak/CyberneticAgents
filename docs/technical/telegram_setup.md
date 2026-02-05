# Telegram Configuration

## Overview
Telegram support can run in one of two modes:
1. Polling mode (default if `TELEGRAM_WEBHOOK_URL` is not set)
2. Webhook mode (recommended for production)

## Required Environment Variables
- `TELEGRAM_BOT_TOKEN`: Bot token from BotFather.
- `TELEGRAM_BOT_USERNAME`: Bot username (without `@`).

## BotFather Setup (Required)
1. Open Telegram and chat with `@BotFather`.
2. Send `/newbot` and follow the prompts to name your bot.
3. Copy the bot token and store it as `TELEGRAM_BOT_TOKEN` (1Password recommended).
4. Save the bot username as `TELEGRAM_BOT_USERNAME`.

If the `qrcode` dependency is installed, onboarding will display QR codes for the
BotFather link and your bot deep link in the terminal.

## Webhook Mode (Optional)
Webhook mode requires a public URL and a secret for validation.

- `TELEGRAM_WEBHOOK_URL`: Public HTTPS URL that Telegram can reach.
- `TELEGRAM_WEBHOOK_SECRET`: Random secret used for webhook validation.
- `TELEGRAM_WEBHOOK_HOST`: Local bind host for the webhook server (default `0.0.0.0`).
- `TELEGRAM_WEBHOOK_PORT`: Local bind port for the webhook server (default `8080`).

## Access Control (Optional)
- `TELEGRAM_ALLOWLIST_CHAT_IDS`: Comma-separated chat IDs allowed to use the bot.
- `TELEGRAM_ALLOWLIST_USER_IDS`: Comma-separated user IDs allowed to use the bot.
- `TELEGRAM_BLOCKLIST_CHAT_IDS`: Comma-separated chat IDs denied access.
- `TELEGRAM_BLOCKLIST_USER_IDS`: Comma-separated user IDs denied access.

Blocklists take precedence over allowlists.

## Pairing (OpenClaw-style)
By default, Telegram messages require pairing approval before they are forwarded.

- `TELEGRAM_PAIRING_ENABLED`: Set to `0` to disable pairing (default is enabled).
- `TELEGRAM_PAIRING_ADMIN_CHAT_IDS`: Comma-separated chat IDs that receive pairing requests
  with inline approve/deny buttons.

When pairing is enabled, the first user to message the bot becomes the admin and is
stored in 1Password under `TELEGRAM_PAIRING_ADMIN_CHAT_IDS`. This bot is private by
default; other users are blocked unless you change the code or configuration.

## 1Password Integration
During onboarding, you can store secrets in the `CyberneticAgents` vault:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`

The onboarding flow will offer to store these secrets when running:

```bash
cyberagent onboarding
```

## Local Development Notes
- Polling mode is simplest for local testing.
- For webhook mode, use a public tunnel and set `TELEGRAM_WEBHOOK_URL` accordingly.

## Quick Verification
Use this log filter to confirm inbound Telegram traffic is being received:
```bash
cyberagent logs --level INFO | rg -n "telegram" -i
```
