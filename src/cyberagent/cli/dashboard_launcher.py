from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def _streamlit_available() -> bool:
    return importlib.util.find_spec("streamlit") is not None


def _python_has_streamlit(python_executable: str) -> bool:
    result = subprocess.run(
        [python_executable, "-c", "import streamlit"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def resolve_dashboard_python() -> str | None:
    if _streamlit_available():
        return sys.executable
    venv_python = Path(__file__).resolve().parents[3] / ".venv" / "bin" / "python"
    if venv_python.exists() and _python_has_streamlit(str(venv_python)):
        return str(venv_python)
    return None
