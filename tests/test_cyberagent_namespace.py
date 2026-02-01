import importlib


def test_core_runtime_shim_exports() -> None:
    old_runtime = importlib.import_module("src.runtime")
    new_runtime = importlib.import_module("src.cyberagent.core.runtime")

    assert new_runtime.get_runtime is old_runtime.get_runtime
    assert new_runtime.stop_runtime is old_runtime.stop_runtime
    assert new_runtime.configure_tracing is old_runtime.configure_tracing


def test_core_logging_shim_exports() -> None:
    old_logging = importlib.import_module("src.logging_utils")
    new_logging = importlib.import_module("src.cyberagent.core.logging")

    assert (
        new_logging.configure_autogen_logging is old_logging.configure_autogen_logging
    )


def test_core_state_shim_exports() -> None:
    old_state = importlib.import_module("src.team_state")
    new_state = importlib.import_module("src.cyberagent.core.state")

    assert new_state.mark_team_active is old_state.mark_team_active
    assert new_state.get_or_create_last_team_id is old_state.get_or_create_last_team_id
