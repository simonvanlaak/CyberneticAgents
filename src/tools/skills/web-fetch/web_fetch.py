#!/usr/bin/env python3
"""Fetch a URL and print readability-optimized HTML."""

import sys


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: web-fetch <url>", file=sys.stderr)
        sys.exit(2)

    import requests

    try:
        from readability import Document  # type: ignore[import]
    except ImportError:
        print("Missing dependency: readability-lxml", file=sys.stderr)
        sys.exit(2)

    url = sys.argv[1]
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    doc = Document(response.text)
    print(doc.summary())


if __name__ == "__main__":
    main()
