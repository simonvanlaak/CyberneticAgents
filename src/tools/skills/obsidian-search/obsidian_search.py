#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="obsidian-search",
        description="Search an Obsidian vault for a query string.",
    )
    parser.add_argument("subcommand", nargs="?", default=None)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--include_filename", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include_content", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--extensions", action="append", default=None, help="Repeatable. Default: .md")
    parser.add_argument("--max_file_bytes", type=int, default=1024 * 1024)
    return parser


def _vault_root() -> Path:
    raw = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not raw:
        raise ValueError("OBSIDIAN_VAULT_PATH is not set")
    root = Path(raw).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"OBSIDIAN_VAULT_PATH does not exist or is not a directory: {root}")
    return root


def _iter_files(root: Path, extensions: list[str]) -> list[Path]:
    exts = set(e if e.startswith(".") else f".{e}" for e in extensions)
    results: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in exts:
            continue
        results.append(path)
    return results


def _safe_read_lines(path: Path, max_bytes: int) -> list[str] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    if st.st_size > max_bytes:
        return None
    try:
        # Use errors=replace to avoid decode exceptions on odd files.
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.subcommand not in (None, "run"):
        print(json.dumps({"error": f"Unknown subcommand: {args.subcommand}"}))
        raise SystemExit(2)

    try:
        root = _vault_root()
    except Exception as exc:
        print(json.dumps({"results": [], "error": str(exc)}))
        raise SystemExit(1)

    query = (args.query or "").strip()
    if not query:
        print(json.dumps({"results": [], "error": "query is required"}))
        raise SystemExit(2)

    q = query.casefold()
    limit = max(1, min(int(args.limit), 100))
    extensions = args.extensions or [".md"]

    candidates = _iter_files(root, extensions)

    scored: list[dict[str, object]] = []
    for path in candidates:
        rel = str(path.relative_to(root))
        score = 0.0
        matches: list[str] = []

        if args.include_filename and q in path.name.casefold():
            score += 2.0
            matches.append(f"filename: {path.name}")

        if args.include_content:
            lines = _safe_read_lines(path, args.max_file_bytes)
            if lines is not None:
                for line in lines:
                    if q in line.casefold():
                        score += 1.0
                        if len(matches) < 5:
                            matches.append(line.strip()[:300])

        if score > 0:
            scored.append({"path": rel, "score": score, "matches": matches})

    scored.sort(key=lambda r: (-float(r.get("score") or 0), str(r.get("path") or "")))
    payload = {"results": scored[:limit]}
    print(json.dumps(payload))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # Allow piping/early close.
        sys.exit(0)
