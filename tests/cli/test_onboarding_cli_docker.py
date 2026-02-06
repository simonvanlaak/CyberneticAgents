from __future__ import annotations

import pytest

from src.cyberagent.cli import onboarding_docker


def test_check_docker_optional_when_no_skills(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(onboarding_docker, "skills_require_docker", lambda: False)
    monkeypatch.setattr(onboarding_docker.shutil, "which", lambda *_: None)

    assert onboarding_docker.check_docker_available() is True
    captured = capsys.readouterr().out
    assert "Continuing without tool execution" in captured


def test_check_cli_tools_image_available_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(onboarding_docker, "skills_require_docker", lambda: True)
    monkeypatch.setattr(onboarding_docker.shutil, "which", lambda *_: "/usr/bin/docker")

    class DummyResult:
        def __init__(self, returncode: int) -> None:
            self.returncode = returncode
            self.stdout = ""
            self.stderr = ""

    def fake_run(*_args: object, **_kwargs: object) -> DummyResult:
        return DummyResult(returncode=1)

    monkeypatch.setattr(onboarding_docker.subprocess, "run", fake_run)

    assert onboarding_docker.check_cli_tools_image_available() is False
    captured = capsys.readouterr().out
    assert "CLI tools image is not available" in captured


def test_check_cli_tools_image_available_permission_denied(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(onboarding_docker, "skills_require_docker", lambda: True)
    monkeypatch.setattr(onboarding_docker.shutil, "which", lambda *_: "/usr/bin/docker")

    class DummyResult:
        def __init__(self, returncode: int, stderr: str) -> None:
            self.returncode = returncode
            self.stdout = ""
            self.stderr = stderr

    def fake_run(*_args: object, **_kwargs: object) -> DummyResult:
        return DummyResult(
            returncode=1,
            stderr="permission denied while trying to connect",
        )

    monkeypatch.setattr(onboarding_docker.subprocess, "run", fake_run)

    assert onboarding_docker.check_cli_tools_image_available() is False
    captured = capsys.readouterr().out.lower()
    assert "permission denied" in captured
    assert "docker group" in captured


def test_check_docker_available_permission_denied(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(onboarding_docker.shutil, "which", lambda *_: "/usr/bin/docker")
    monkeypatch.setattr(onboarding_docker, "skills_require_docker", lambda: True)

    class DummyResult:
        def __init__(self, returncode: int, stderr: str) -> None:
            self.returncode = returncode
            self.stdout = ""
            self.stderr = stderr

    def fake_run(*_args: object, **_kwargs: object) -> DummyResult:
        return DummyResult(
            returncode=1,
            stderr="Permission denied while trying to connect to the Docker API",
        )

    monkeypatch.setattr(onboarding_docker.subprocess, "run", fake_run)

    assert onboarding_docker.check_docker_available() is False
    captured = capsys.readouterr().out.lower()
    assert "cannot access the daemon" in captured
    assert "docker group" in captured
