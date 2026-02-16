"""python -m entrypoint for cyberagent CLI."""

from __future__ import annotations

from src.cyberagent.cli.cyberagent import main

if __name__ == "__main__":
    raise SystemExit(main())
