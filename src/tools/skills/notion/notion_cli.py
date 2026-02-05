#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib.parse import urlencode

import requests

DEFAULT_NOTION_VERSION = "2025-09-03"
NOTION_API_BASE = "https://api.notion.com"


def build_url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    cleaned = path if path.startswith("/") else f"/{path}"
    return f"{NOTION_API_BASE}{cleaned}"


def parse_query_args(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Invalid query entry '{item}'. Use key=value.")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid query entry '{item}'. Use key=value.")
        parsed[key] = value
    return parsed


def build_headers(api_key: str, version: str, has_body: bool) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": version,
    }
    if has_body:
        headers["Content-Type"] = "application/json"
    return headers


def load_api_key() -> str:
    api_key = os.environ.get("NOTION_API_KEY")
    if api_key:
        return api_key
    raise ValueError("NOTION_API_KEY is required.")


def parse_body(body: str | None) -> Any | None:
    if not body:
        return None
    return json.loads(body)


def run_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: Any | None,
    timeout: int,
) -> requests.Response:
    return requests.request(
        method=method,
        url=url,
        headers=headers,
        json=body,
        timeout=timeout,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Notion API CLI wrapper.")
    parser.add_argument("--method", default="POST", help="HTTP method.")
    parser.add_argument("--path", required=True, help="API path or full URL.")
    parser.add_argument("--body", help="JSON string body.")
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="Query parameter in key=value form (repeatable).",
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_NOTION_VERSION,
        help="Notion API version header.",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        api_key = load_api_key()
        query_params = parse_query_args(args.query)
        url = build_url(args.path)
        if query_params:
            url = f"{url}?{urlencode(query_params)}"
        body = parse_body(args.body)
        headers = build_headers(api_key, args.version, has_body=body is not None)
        response = run_request(
            method=str(args.method).upper(),
            url=url,
            headers=headers,
            body=body,
            timeout=args.timeout,
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    try:
        payload = response.json()
    except ValueError:
        payload = {"text": response.text}
    output = {
        "status_code": response.status_code,
        "ok": response.ok,
        "response": payload,
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
