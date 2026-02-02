from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace
from typing import List, Type

import pytest

from src.cyberagent.tools.cli_executor import git_readonly_sync


def _load_web_fetch(
    monkeypatch: pytest.MonkeyPatch, document_factory: Type[object]
) -> ModuleType:
    monkeypatch.setitem(
        sys.modules, "readability", SimpleNamespace(Document=document_factory)
    )
    module = importlib.import_module("src.cyberagent.tools.cli_executor.web_fetch")
    return importlib.reload(module)


def _load_web_search(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = importlib.import_module("src.cyberagent.tools.cli_executor.web_search")
    return importlib.reload(module)


def test_web_fetch_requires_url(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["web-fetch"])

    web_fetch = _load_web_fetch(monkeypatch, object)

    with pytest.raises(SystemExit) as excinfo:
        web_fetch.main()

    assert excinfo.value.code == 2
    assert "Usage: web-fetch <url>" in capsys.readouterr().err


def test_web_fetch_outputs_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["web-fetch", "https://example.com"])

    def _fake_get(url: str, timeout: int) -> SimpleNamespace:
        assert url == "https://example.com"
        assert timeout == 20
        return SimpleNamespace(
            text="<html>content</html>", raise_for_status=lambda: None
        )

    class _FakeDocument:
        def __init__(self, html: str) -> None:
            self.html = html

        def summary(self) -> str:
            return "<p>summary</p>"

    web_fetch = _load_web_fetch(monkeypatch, _FakeDocument)
    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(get=_fake_get))

    web_fetch.main()

    assert capsys.readouterr().out.strip() == "<p>summary</p>"


def test_web_search_requires_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["web_search", "run", "--query", "cats"],
    )
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)

    web_search = _load_web_search(monkeypatch)

    with pytest.raises(SystemExit) as excinfo:
        web_search.main()

    assert "BRAVE_API_KEY" in str(excinfo.value)


def test_web_search_outputs_results(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "web_search",
            "run",
            "--query",
            "cats",
            "--count",
            "5",
            "--offset",
            "1",
            "--freshness",
            "day",
        ],
    )
    monkeypatch.setenv("BRAVE_API_KEY", "token")

    def _fake_get(url: str, headers: dict[str, str], params: dict[str, object]):
        assert url == "https://api.search.brave.com/res/v1/web/search"
        assert headers["X-Subscription-Token"] == "token"
        assert params == {
            "q": "cats",
            "count": 5,
            "offset": 1,
            "freshness": "day",
        }

        class _Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"web": {"results": [{"title": "Cats"}]}}

        return _Response()

    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(get=_fake_get))

    web_search = _load_web_search(monkeypatch)
    web_search.main()

    assert '"title": "Cats"' in capsys.readouterr().out


def test_build_authed_url_adds_token() -> None:
    url = "https://github.com/org/repo.git"

    authed = git_readonly_sync._build_authed_url(url, "token123", None)

    assert authed == "https://x-access-token:token123@github.com/org/repo.git"


def test_build_authed_url_ignores_ssh() -> None:
    url = "git@github.com:org/repo.git"

    authed = git_readonly_sync._build_authed_url(url, "token123", None)

    assert authed == url


def test_git_readonly_sync_requires_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "git-readonly-sync",
            "--repo",
            "repo",
            "--dest",
            "out",
            "--token-env",
            "TOKEN",
        ],
    )
    monkeypatch.delenv("TOKEN", raising=False)

    with pytest.raises(SystemExit) as excinfo:
        git_readonly_sync.main()

    assert "Missing required token in env var TOKEN." in str(excinfo.value)


def test_git_readonly_sync_clone_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: List[List[str]] = []

    def _record(args: list[str], cwd: str | None = None) -> None:
        calls.append(args)

    monkeypatch.setenv("TOKEN", "tok")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "git-readonly-sync",
            "--repo",
            "https://github.com/org/repo.git",
            "--dest",
            "out",
            "--token-env",
            "TOKEN",
        ],
    )
    monkeypatch.setattr(git_readonly_sync.os.path, "isdir", lambda _path: False)
    monkeypatch.setattr(git_readonly_sync, "_run_git", _record)

    git_readonly_sync.main()

    assert calls[0][:3] == ["clone", "--depth", "1"]
    assert calls[1] == ["checkout", "main"]
    assert calls[2] == ["reset", "--hard", "origin/main"]
    assert "x-access-token:tok@github.com" in calls[0][3]


def test_git_readonly_sync_fetch_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: List[List[str]] = []

    def _record(args: list[str], cwd: str | None = None) -> None:
        calls.append(args)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "git-readonly-sync",
            "--repo",
            "https://github.com/org/repo.git",
            "--dest",
            "out",
        ],
    )
    monkeypatch.setattr(git_readonly_sync.os.path, "isdir", lambda _path: True)
    monkeypatch.setattr(git_readonly_sync, "_run_git", _record)

    git_readonly_sync.main()

    assert calls[0] == ["fetch", "--prune", "origin"]
    assert calls[1] == ["checkout", "main"]
    assert calls[2] == ["reset", "--hard", "origin/main"]
