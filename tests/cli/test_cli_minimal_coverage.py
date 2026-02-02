from src.cyberagent.cli.cyberagent import build_parser


def test_build_parser_parses_basic_commands() -> None:
    parser = build_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"

    args = parser.parse_args(["logs"])
    assert args.command == "logs"

    args = parser.parse_args(["start", "-m", "hello"])
    assert args.command == "start"
    assert args.message == "hello"
