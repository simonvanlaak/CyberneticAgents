from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Mapping


class TelegramClient:
    def __init__(self, token: str, base_url: str | None = None) -> None:
        self._token = token
        self._base_url = base_url or f"https://api.telegram.org/bot{token}"

    def get_updates(
        self, offset: int | None = None, timeout: int = 20
    ) -> list[dict[str, object]]:
        params: dict[str, object] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        payload = self._post("getUpdates", params)
        result = payload.get("result")
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        return []

    def send_message(self, chat_id: int, text: str) -> None:
        payload = self._post("sendMessage", {"chat_id": chat_id, "text": text})
        if not payload.get("ok", False):
            raise RuntimeError("Telegram sendMessage failed.")

    def _post(self, method: str, params: Mapping[str, object]) -> dict[str, object]:
        endpoint = f"{self._base_url}/{method}"
        data = urllib.parse.urlencode(params).encode()
        request = urllib.request.Request(
            endpoint,
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("Telegram API returned invalid payload.")
        return payload
