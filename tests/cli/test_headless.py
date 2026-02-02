import pytest

from src.cyberagent.cli import headless


@pytest.mark.asyncio
async def test_run_headless_session_starts_cli_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: dict[str, bool] = {"value": False}
    stopped: dict[str, bool] = {"value": False}

    async def fake_start_cli_executor() -> None:
        started["value"] = True

    async def fake_stop_runtime() -> None:
        stopped["value"] = True

    async def fake_register() -> None:
        return None

    class DummyEnforcer:
        def clear_policy(self) -> None:
            return None

    class DummyRuntime:
        async def send_message(self, *args, **kwargs):  # noqa: ANN001
            return None

    async def fake_read_stdin(queue, stop_event):  # noqa: ANN001
        stop_event.set()

    async def fake_forward(queue, runtime, recipient, stop_event):  # noqa: ANN001
        return None

    monkeypatch.setattr(headless, "init_db", lambda: None)
    monkeypatch.setattr(headless, "register_systems", fake_register)
    monkeypatch.setattr(headless, "get_enforcer", lambda: DummyEnforcer())
    monkeypatch.setattr(headless, "configure_autogen_logging", lambda _dir: None)
    monkeypatch.setattr(headless, "get_runtime", lambda: DummyRuntime())
    monkeypatch.setattr(headless, "read_stdin_loop", fake_read_stdin)
    monkeypatch.setattr(headless, "forward_user_messages", fake_forward)
    monkeypatch.setattr(headless, "start_cli_executor", fake_start_cli_executor)
    monkeypatch.setattr(headless, "stop_runtime", fake_stop_runtime)

    await headless.run_headless_session()

    assert started["value"] is True
    assert stopped["value"] is True
