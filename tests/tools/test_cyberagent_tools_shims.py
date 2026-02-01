import importlib


def test_cli_executor_shim_exports() -> None:
    old_factory = importlib.import_module("src.tools.cli_executor.factory")
    new_factory = importlib.import_module("src.cyberagent.tools.cli_executor.factory")

    assert old_factory.create_cli_executor is new_factory.create_cli_executor
