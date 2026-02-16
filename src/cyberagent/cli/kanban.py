from __future__ import annotations

import os
import webbrowser

from src.cyberagent.cli.message_catalog import get_message


def _resolve_taiga_ui_url() -> str:
    explicit = os.getenv("TAIGA_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")

    site_domain = os.getenv("TAIGA_SITES_DOMAIN", "").strip()
    if site_domain:
        if site_domain.startswith(("http://", "https://")):
            return site_domain.rstrip("/")
        return f"http://{site_domain.rstrip('/')}"

    public_port = os.getenv("TAIGA_PUBLIC_PORT", "").strip() or "9000"
    if public_port.isdigit():
        return f"http://127.0.0.1:{public_port}"
    return "http://127.0.0.1:9000"


def handle_kanban_command() -> int:
    taiga_url = _resolve_taiga_ui_url()
    print(get_message("cyberagent", "kanban_opening", taiga_url=taiga_url))
    try:
        opened = webbrowser.open_new_tab(taiga_url)
    except webbrowser.Error:
        opened = False
    if not opened:
        print(get_message("cyberagent", "kanban_open_manual", taiga_url=taiga_url))
    return 0
