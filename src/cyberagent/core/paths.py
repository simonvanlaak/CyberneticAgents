from __future__ import annotations

import os
from pathlib import Path

ENV_ROOT_KEY = "CYBERAGENT_ROOT"


def _repo_root_from_module() -> Path | None:
    try:
        return Path(__file__).resolve().parents[3]
    except IndexError:
        return None


def get_repo_root() -> Path | None:
    env_root = os.environ.get(ENV_ROOT_KEY)
    if env_root:
        return Path(env_root).expanduser().resolve()
    return _repo_root_from_module()


def get_data_dir() -> Path:
    repo_root = get_repo_root()
    if repo_root is None:
        return Path.cwd() / "data"
    return repo_root / "data"


def get_logs_dir() -> Path:
    repo_root = get_repo_root()
    if repo_root is None:
        return Path.cwd() / "logs"
    return repo_root / "logs"


def resolve_data_path(*parts: str) -> Path:
    return get_data_dir().joinpath(*parts)


def resolve_logs_path(*parts: str) -> Path:
    return get_logs_dir().joinpath(*parts)
