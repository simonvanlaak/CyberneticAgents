# -*- coding: utf-8 -*-
"""
Main Application Entry Point (CLI)

CLI-based interface for interacting with the multi-agent runtime.
"""

import argparse
import asyncio
import sys

import dotenv

from src.cyberagent.cli.headless import run_headless_session

dotenv.load_dotenv()


def parse_cli_args(argv: list[str]) -> str | None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", dest="message", type=str, default=None)
    parser.add_argument("message_parts", nargs="*")
    args = parser.parse_args(argv[1:])

    if args.message:
        initial_message = args.message.strip()
    else:
        initial_message = " ".join(args.message_parts).strip()

    return initial_message or None


async def main() -> None:
    initial_message = parse_cli_args(sys.argv)
    await run_headless_session(initial_message)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        from src.cyberagent.cli.status import main as status_main

        raise SystemExit(status_main(sys.argv[2:]))
    asyncio.run(main())
