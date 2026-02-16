from __future__ import annotations

import os
import webbrowser

from src.cyberagent.cli.message_catalog import get_message


def _resolve_planka_ui_url() -> str:
    """Resolve the Planka UI URL from environment variables."""
    explicit = os.getenv("PLANKA_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")

    public_port = os.getenv("PLANKA_PUBLIC_PORT", "").strip() or "3000"
    if public_port.isdigit():
        return f"http://127.0.0.1:{public_port}"
    return "http://127.0.0.1:3000"


def handle_kanban_command() -> int:
    planka_url = _resolve_planka_ui_url()
    print(get_message("cyberagent", "kanban_opening", planka_url=planka_url))
    try:
        opened = webbrowser.open_new_tab(planka_url)
    except webbrowser.Error:
        opened = False
    if not opened:
        print(get_message("cyberagent", "kanban_open_manual", planka_url=planka_url))
    return 0
