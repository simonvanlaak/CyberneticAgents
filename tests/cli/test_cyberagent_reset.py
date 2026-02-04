from __future__ import annotations

import argparse

import pytest

from src.cyberagent.cli import cyberagent


def test_reset_command_calls_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_stop(_: argparse.Namespace) -> int:
        calls.append("stop")
        return 0

    monkeypatch.setattr(cyberagent, "_handle_stop", fake_stop)
    monkeypatch.setattr(cyberagent, "_reset_data_dir", lambda *_: None)
    monkeypatch.setattr(cyberagent, "_remove_dir", lambda *_: None)

    exit_code = cyberagent.main(["reset", "--yes"])

    assert exit_code == 0
    assert calls == ["stop"]
