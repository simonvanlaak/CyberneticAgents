from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _load_compose() -> dict[str, Any]:
    compose_path = Path(__file__).resolve().parents[1] / "docker-compose.yml"
    assert compose_path.exists(), "Expected unified docker-compose.yml at repo root."
    payload = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), "Compose file must parse as a mapping."
    return payload


def test_unified_compose_contains_taiga_and_cyberagent_services() -> None:
    compose_payload = _load_compose()
    services = compose_payload.get("services")
    assert isinstance(services, dict)

    for service_name in {"taiga-db", "taiga-back", "taiga-front", "cyberagent"}:
        assert service_name in services


def test_cyberagent_service_uses_long_running_runtime_command() -> None:
    compose_payload = _load_compose()
    services = compose_payload.get("services")
    assert isinstance(services, dict)

    cyberagent_service = services.get("cyberagent")
    assert isinstance(cyberagent_service, dict)

    command = cyberagent_service.get("command")
    assert command is not None, "cyberagent service should define an explicit command."

    if isinstance(command, list):
        normalized = " ".join(str(part) for part in command)
    else:
        normalized = str(command)

    assert "serve" in normalized
