from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def send_message(chat_id: int, text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = response.read().decode("utf-8")
    payload = json.loads(data)
    if not payload.get("ok", False):
        raise RuntimeError("Telegram sendMessage failed.")


def send_message_with_inline_keyboard(
    chat_id: int, text: str, buttons: list[tuple[str, str]]
) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    keyboard = [[{"text": label, "callback_data": value} for label, value in buttons]]
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": json.dumps({"inline_keyboard": keyboard}),
        }
    ).encode()
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = response.read().decode("utf-8")
    payload = json.loads(data)
    if not payload.get("ok", False):
        raise RuntimeError("Telegram sendMessage failed.")
