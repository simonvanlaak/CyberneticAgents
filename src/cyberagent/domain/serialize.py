from __future__ import annotations

from typing import Any


def model_to_dict(model: Any) -> dict[str, Any]:
    """
    Convert a SQLAlchemy model to a JSON-friendly dict.

    Strips SQLAlchemy instance state and normalizes Enum-like values.
    """
    payload: dict[str, Any] = {}
    for key, value in model.__dict__.items():
        if key.startswith("_sa_instance_state"):
            continue
        if hasattr(value, "value"):
            payload[key] = value.value
        else:
            payload[key] = value
    return payload
