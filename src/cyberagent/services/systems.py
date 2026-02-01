"""System lookup helpers."""

from src.cyberagent.db.models.system import (
    get_system as _get_system,
    get_system_by_type as _get_system_by_type,
    get_systems_by_type as _get_systems_by_type,
    ensure_default_systems_for_team as _ensure_default_systems_for_team,
)


def get_system(system_id: int):
    """Return a system by id."""
    return _get_system(system_id)


def get_system_by_type(team_id: int, system_type: int):
    """Return a system by type for a team."""
    return _get_system_by_type(team_id, system_type)


def get_systems_by_type(team_id: int, system_type: int):
    """Return systems by type for a team."""
    return _get_systems_by_type(team_id, system_type)


def ensure_default_systems_for_team(team_id: int):
    """Ensure default systems exist for a team."""
    return _ensure_default_systems_for_team(team_id)
