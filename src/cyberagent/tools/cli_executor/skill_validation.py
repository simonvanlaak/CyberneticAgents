"""Skill package validation helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path


def validate_skills(skills_root: Path | str) -> None:
    """
    Validate skill packages with the Agent Skills reference validator.

    Args:
        skills_root: Root directory that contains skill packages.

    Raises:
        RuntimeError: If the validator is missing or returns a failure.
    """
    root = str(Path(skills_root))
    try:
        result = subprocess.run(
            ["skills-ref", "validate", root],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "skills-ref validator is required. Install it and retry."
        ) from exc

    if result.returncode != 0:
        raise RuntimeError(
            "skills-ref validation failed: "
            f"{result.stdout.strip()} {result.stderr.strip()}".strip()
        )
