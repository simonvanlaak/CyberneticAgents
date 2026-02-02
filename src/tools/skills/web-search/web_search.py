#!/usr/bin/env python3
"""Brave Search CLI wrapper for web_search tool."""

import argparse
import json
import os

API_URL = "https://api.search.brave.com/res/v1/web/search"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Brave web search CLI wrapper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a web search query.")
    run_parser.add_argument("--query", required=True, help="Search query.")
    run_parser.add_argument("--count", type=int, default=None, help="Result count.")
    run_parser.add_argument("--offset", type=int, default=None, help="Result offset.")
    run_parser.add_argument(
        "--freshness",
        default=None,
        help="Result freshness filter (day, week, month, year).",
    )
    return parser


def _require_api_key() -> str:
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        raise SystemExit("Missing required BRAVE_API_KEY environment variable.")
    return api_key


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command != "run":
        raise SystemExit(f"Unsupported command: {args.command}")

    api_key = _require_api_key()

    import requests

    params: dict[str, str] = {"q": args.query}
    if args.count is not None:
        params["count"] = str(args.count)
    if args.offset is not None:
        params["offset"] = str(args.offset)
    if args.freshness is not None:
        params["freshness"] = args.freshness

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }

    response = requests.get(API_URL, headers=headers, params=params)
    response.raise_for_status()
    print(json.dumps(response.json()))


if __name__ == "__main__":
    main()
