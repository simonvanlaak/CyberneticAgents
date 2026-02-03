"""Post-processing helpers for STT transcripts."""

from __future__ import annotations

from typing import Iterable


def format_timestamped_text(
    text: str,
    segments: Iterable[dict[str, object]],
    *,
    threshold_chars: int = 200,
) -> str:
    """
    Inject timestamps into long transcripts using segment timing data.

    Args:
        text: The raw transcript text.
        segments: Segment payloads with start offsets and text.
        threshold_chars: Minimum length before timestamps are injected.

    Returns:
        Timestamped transcript when long enough; otherwise the original text.
    """
    if len(text) < threshold_chars:
        return text
    lines: list[str] = []
    for segment in segments:
        start = segment.get("start")
        snippet = segment.get("text")
        if not isinstance(start, (int, float)) or not isinstance(snippet, str):
            continue
        snippet = snippet.strip()
        if not snippet:
            continue
        lines.append(f"[{_format_timestamp(start)}] {snippet}")
    return "\n".join(lines) if lines else text


def _format_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
