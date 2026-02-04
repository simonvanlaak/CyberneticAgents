"""Transcription CLI helpers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.cyberagent.stt.transcribe import transcribe_file
from src.cyberagent.cli.message_catalog import get_message


def add_transcribe_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> argparse.ArgumentParser:
    """
    Register the transcribe subcommand.

    Args:
        subparsers: The main CLI subparser collection.

    Returns:
        The parser configured for the transcribe command.
    """
    parser = subparsers.add_parser("transcribe", help="Transcribe an audio file.")
    parser.add_argument("file", type=str, help="Path to audio file.")
    return parser


def handle_transcribe(args: argparse.Namespace) -> int:
    """
    Handle the transcribe CLI command.

    Args:
        args: Parsed CLI arguments for the transcribe command.

    Returns:
        Exit code for the CLI command.
    """
    file_path = Path(args.file)
    if not file_path.exists():
        print(
            get_message("transcribe", "file_not_found", path=file_path),
            file=sys.stderr,
        )
        return 2
    try:
        result = transcribe_file(file_path)
    except Exception as exc:
        print(
            get_message("transcribe", "transcription_failed", error=exc),
            file=sys.stderr,
        )
        return 2
    if result.low_confidence:
        print(get_message("transcribe", "low_confidence"), file=sys.stderr)
    print(result.text)
    return 0
