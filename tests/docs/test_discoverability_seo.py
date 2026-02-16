from __future__ import annotations

from pathlib import Path


def test_readme_contains_discoverability_keywords_and_badges() -> None:
    readme_path = Path(__file__).resolve().parents[2] / "README.md"
    content = readme_path.read_text(encoding="utf-8").lower()

    expected_keywords = [
        "cybernetics",
        "stafford beer",
        "viable systems model",
        "systems theory",
        "autogen",
        "casbin",
        "rbac",
        "taiga",
    ]

    for keyword in expected_keywords:
        assert keyword in content

    assert "[![python" in content
    assert "[![license" in content


def test_docs_discoverability_and_indexes_exist() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    discoverability_doc = repo_root / "docs" / "discoverability.md"
    docs_index = repo_root / "docs" / "README.md"

    assert discoverability_doc.exists(), "Expected docs/discoverability.md"
    assert docs_index.exists(), "Expected docs/README.md index"

    discoverability_content = discoverability_doc.read_text(encoding="utf-8").lower()
    for keyword in ["cybernetics", "stafford beer", "viable systems model"]:
        assert keyword in discoverability_content

    docs_index_content = docs_index.read_text(encoding="utf-8").lower()
    assert "technical" in docs_index_content
    assert "features" in docs_index_content
