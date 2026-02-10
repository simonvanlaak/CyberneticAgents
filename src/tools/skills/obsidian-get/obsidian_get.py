#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="obsidian-get",
        description="Read an Obsidian note from the configured vault.",
    )
    parser.add_argument("subcommand", nargs="?", default=None)
    parser.add_argument("--path", required=True, help="Relative path within the vault")
    parser.add_argument("--max_chars", type=int, default=20000)
    return parser


def _vault_root() -> Path:
    raw = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not raw:
        raise ValueError("OBSIDIAN_VAULT_PATH is not set")
    root = Path(raw).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"OBSIDIAN_VAULT_PATH does not exist or is not a directory: {root}")
    return root


def _resolve_within(root: Path, rel: str) -> Path:
    # Disallow absolute paths.
    p = Path(rel)
    if p.is_absolute():
        raise ValueError("path must be relative to the vault")
    candidate = (root / p).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("path escapes vault root") from exc
    return candidate


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.subcommand not in (None, "run"):
        print(json.dumps({"error": f"Unknown subcommand: {args.subcommand}"}))
        raise SystemExit(2)

    try:
        root = _vault_root()
        path = _resolve_within(root, args.path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Note not found: {args.path}")
        content = path.read_text(encoding="utf-8", errors="replace")
        max_chars = max(1000, min(int(args.max_chars), 200000))
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]
        payload = {
            "path": str(Path(args.path)),
            "content": content,
            "truncated": truncated,
        }
        print(json.dumps(payload))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
