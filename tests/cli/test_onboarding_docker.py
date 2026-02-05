from __future__ import annotations

import pytest

from src.cyberagent.cli import onboarding_docker


def test_check_docker_available_attempts_start_when_unreachable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(onboarding_docker, "skills_require_docker", lambda: True)

    def fake_which(name: str) -> str | None:
        if name == "docker":
            return "/usr/bin/docker"
        if name == "systemctl":
            return "/bin/systemctl"
        return None

    monkeypatch.setattr(onboarding_docker.shutil, "which", fake_which)

    class DummyResult:
        def __init__(self, returncode: int, stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = ""
            self.stderr = stderr

    docker_info_calls = 0

    def fake_run(cmd: list[str], **_kwargs: object) -> DummyResult:
        nonlocal docker_info_calls
        if cmd[:2] == ["/usr/bin/docker", "info"]:
            docker_info_calls += 1
            if docker_info_calls == 1:
                return DummyResult(
                    returncode=1,
                    stderr="Cannot connect to the Docker daemon",
                )
            return DummyResult(returncode=0)
        if cmd[:3] == ["/bin/systemctl", "start", "docker"]:
            return DummyResult(returncode=0)
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(onboarding_docker.subprocess, "run", fake_run)

    assert onboarding_docker.check_docker_available() is True
    captured = capsys.readouterr().out.lower()
    assert "attempting to start it" in captured


def test_check_docker_available_start_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(onboarding_docker, "skills_require_docker", lambda: True)

    def fake_which(name: str) -> str | None:
        if name == "docker":
            return "/usr/bin/docker"
        if name == "systemctl":
            return "/bin/systemctl"
        return None

    monkeypatch.setattr(onboarding_docker.shutil, "which", fake_which)

    class DummyResult:
        def __init__(self, returncode: int, stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = ""
            self.stderr = stderr

    def fake_run(cmd: list[str], **_kwargs: object) -> DummyResult:
        if cmd[:2] == ["/usr/bin/docker", "info"]:
            return DummyResult(
                returncode=1,
                stderr="Cannot connect to the Docker daemon",
            )
        if cmd[:3] == ["/bin/systemctl", "start", "docker"]:
            return DummyResult(returncode=1)
        if cmd[:4] == ["/bin/systemctl", "--user", "start", "docker"]:
            return DummyResult(returncode=1)
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(onboarding_docker.subprocess, "run", fake_run)

    assert onboarding_docker.check_docker_available() is False
    captured = capsys.readouterr().out.lower()
    assert "unable to start the docker daemon automatically" in captured
