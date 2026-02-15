from __future__ import annotations

from pathlib import Path

import pytest


WORKFLOW_DIR = Path(".github/workflows")


@pytest.mark.parametrize("workflow_path", sorted(WORKFLOW_DIR.glob("*.yml")))
def test_workflows_define_explicit_permissions(workflow_path: Path) -> None:
    content = workflow_path.read_text(encoding="utf-8")
    assert "permissions:" in content, (
        f"{workflow_path} must declare an explicit permissions block for GITHUB_TOKEN."
    )
