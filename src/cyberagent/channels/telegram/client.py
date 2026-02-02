from __future__ import annotations

import json
import os
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

    def get_file_path(self, file_id: str) -> str:
        payload = self._post("getFile", {"file_id": file_id})
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("Telegram getFile returned invalid payload.")
        file_path = result.get("file_path")
        if not isinstance(file_path, str) or not file_path:
            raise RuntimeError("Telegram getFile missing file_path.")
        return file_path

    def download_file(
        self, file_path: str, destination: os.PathLike[str] | str
    ) -> None:
        file_url = f"{self._base_url.replace('/bot', '/file/bot')}/{file_path}"
        request = urllib.request.Request(file_url, method="GET")
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
        with open(destination, "wb") as handle:
            handle.write(payload)

    def set_webhook(self, url: str, secret: str | None = None) -> None:
        params: dict[str, object] = {"url": url}
        if secret:
            params["secret_token"] = secret
        payload = self._post("setWebhook", params)
        if not payload.get("ok", False):
            raise RuntimeError("Telegram setWebhook failed.")

    def delete_webhook(self) -> None:
        payload = self._post("deleteWebhook", {})
        if not payload.get("ok", False):
            raise RuntimeError("Telegram deleteWebhook failed.")

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
