from __future__ import annotations

from pathlib import Path

from src.rbac.authz_db import resolve_authz_db_url


def test_resolve_authz_db_url_prefers_shared_env(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    shared = tmp_path / "shared_authz.db"
    monkeypatch.setenv("CYBERAGENT_AUTHZ_DB_URL", f"sqlite:///{shared}")
    monkeypatch.setenv(
        "CYBERAGENT_SKILL_PERMISSIONS_DB_URL",
        f"sqlite:///{tmp_path / 'skill.db'}",
    )

    db_url = resolve_authz_db_url(
        specific_env="CYBERAGENT_SKILL_PERMISSIONS_DB_URL",
        default_filename="skill_permissions.db",
    )

    assert db_url == f"sqlite:///{shared}"


def test_resolve_authz_db_url_falls_back_to_specific_env(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("CYBERAGENT_AUTHZ_DB_URL", raising=False)
    specific = tmp_path / "specific.db"
    monkeypatch.setenv("CYBERAGENT_RBAC_DB_URL", f"sqlite:///{specific}")

    db_url = resolve_authz_db_url(
        specific_env="CYBERAGENT_RBAC_DB_URL",
        default_filename="rbac.db",
    )

    assert db_url == f"sqlite:///{specific}"
