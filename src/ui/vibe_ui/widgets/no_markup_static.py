"""Derived from Mistral Vibe (Apache 2.0). See third_party/mistral-vibe/LICENSE."""

from __future__ import annotations

from typing import Any
from textual.widgets import Static


class NoMarkupStatic(Static):
    def __init__(self, content: Any = "", **kwargs: Any) -> None:
        super().__init__(content, markup=False, **kwargs)
