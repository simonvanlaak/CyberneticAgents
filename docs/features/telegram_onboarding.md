# Telegram Onboarding (Self-Admin)

## Summary
Telegram onboarding is designed for a single owner who creates their own bot. The
first user to message the bot becomes the admin and is stored in 1Password.
Additional users are blocked by default.

## User Journey
1. Run `cyberagent onboarding`.
2. Follow the BotFather steps to create a bot and paste the token (stored in 1Password).
3. Provide the bot username (stored in 1Password).
4. Scan the BotFather QR (optional) to open BotFather quickly.
5. Scan the bot deep-link QR (optional) and send the first message.
6. The first message auto-registers the user as the admin chat.

## Behavior
- Self-admin bootstrap:
  - If no admin chat ID is configured, the first Telegram user becomes admin.
  - The admin chat ID is stored in 1Password under `TELEGRAM_PAIRING_ADMIN_CHAT_IDS`.
- Private by default:
  - Any other user receives a "private bot" message and is not forwarded.
- QR codes:
  - BotFather QR is shown during onboarding setup.
  - Bot deep-link QR is shown when prompting for the first message.

## Configuration
Required:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BOT_USERNAME` (without `@`)

Optional:
- `TELEGRAM_PAIRING_ENABLED` (default enabled)
- `TELEGRAM_PAIRING_ADMIN_CHAT_IDS` (auto-set for the first user)

## Notes
- QR rendering requires the `qrcode` dependency.
- Admin chat IDs are stored in 1Password only (never `.env`).
