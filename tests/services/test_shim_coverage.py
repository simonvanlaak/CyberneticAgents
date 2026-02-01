import importlib


def test_runtime_shim_exports() -> None:
    runtime_shim = importlib.import_module("src.runtime")
    core_runtime = importlib.import_module("src.cyberagent.core.runtime")

    assert runtime_shim.get_runtime is core_runtime.get_runtime


def test_cli_executor_shims() -> None:
    old_factory = importlib.import_module("src.tools.cli_executor.factory")
    new_factory = importlib.import_module("src.cyberagent.tools.cli_executor.factory")
    assert old_factory.create_cli_executor is new_factory.create_cli_executor

    old_cli = importlib.import_module("src.cli.cyberagent")
    new_cli = importlib.import_module("src.cyberagent.cli.cyberagent")
    assert old_cli.build_parser is new_cli.build_parser

    old_secrets = importlib.import_module("src.tools.cli_executor.secrets")
    new_secrets = importlib.import_module("src.cyberagent.tools.cli_executor.secrets")
    assert old_secrets.get_tool_secrets is new_secrets.get_tool_secrets

    old_executor = importlib.import_module("src.tools.cli_executor.docker_env_executor")
    new_executor = importlib.import_module(
        "src.cyberagent.tools.cli_executor.docker_env_executor"
    )
    assert (
        old_executor.EnvDockerCommandLineCodeExecutor
        is new_executor.EnvDockerCommandLineCodeExecutor
    )

    old_tool = importlib.import_module("src.tools.cli_executor.openclaw_tool")
    new_tool = importlib.import_module(
        "src.cyberagent.tools.cli_executor.openclaw_tool"
    )
    assert old_tool.OpenClawTool is new_tool.OpenClawTool
