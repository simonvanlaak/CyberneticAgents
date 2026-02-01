import importlib


def test_cli_shim_exports() -> None:
    old_cli = importlib.import_module("src.cli.cyberagent")
    new_cli = importlib.import_module("src.cyberagent.cli.cyberagent")

    assert old_cli.build_parser is new_cli.build_parser
