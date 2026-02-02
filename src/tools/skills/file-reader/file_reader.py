#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="file-reader",
        description="Run a read-only shell command inside the tool container.",
    )
    parser.add_argument("subcommand", nargs="?", default=None)
    parser.add_argument(
        "--command",
        required=True,
        help='Shell command to run (e.g. "ls -la" or "sed -n \'1,50p\' file.txt").',
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.subcommand not in (None, "run"):
        print(f"Unknown subcommand: {args.subcommand}", file=sys.stderr)
        raise SystemExit(2)

    result = subprocess.run(
        args.command,
        shell=True,
        check=False,
        text=True,
        capture_output=True,
    )
    payload: dict[str, object] = {
        "output": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
    }
    print(json.dumps(payload))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
