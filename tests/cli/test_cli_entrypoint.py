from pathlib import Path


def test_pyproject_declares_cyberagent_script() -> None:
    pyproject = Path("pyproject.toml")
    assert pyproject.exists()
    content = pyproject.read_text(encoding="utf-8")
    assert "[project.scripts]" in content
    assert 'cyberagent = "src.cyberagent.cli.cyberagent:main"' in content
