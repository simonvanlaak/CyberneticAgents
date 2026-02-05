from __future__ import annotations

from io import StringIO

from src.cyberagent.secrets import get_secret


def build_bot_link() -> str | None:
    """
    Build the Telegram deep link for the configured bot.

    Returns:
        Bot link in the form https://t.me/<username>, or None if unavailable.
    """
    username = get_secret("TELEGRAM_BOT_USERNAME")
    if not username:
        return None
    cleaned = username.strip().lstrip("@")
    if not cleaned:
        return None
    return f"https://t.me/{cleaned}"


def botfather_link() -> str:
    return "https://t.me/BotFather"


def render_telegram_qr(link: str) -> str | None:
    """
    Render a Telegram deep link QR code as ASCII.

    Args:
        link: Telegram deep link.

    Returns:
        ASCII QR code string or None if QR rendering is unavailable.
    """
    try:
        import qrcode  # type: ignore[import]
    except ImportError:
        return None
    qr = qrcode.QRCode(border=1)
    qr.add_data(link)
    qr.make(fit=True)
    buffer = StringIO()
    qr.print_ascii(out=buffer, invert=True)
    return buffer.getvalue().strip()
