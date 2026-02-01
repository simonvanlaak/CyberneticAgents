"""Domain defaults for system registration."""

from typing import List, Tuple

from src.enums import SystemType

DEFAULT_SYSTEM_SPECS: List[Tuple[SystemType, str]] = [
    (SystemType.OPERATION, "System1/root"),
    (SystemType.CONTROL, "System3/root"),
    (SystemType.INTELLIGENCE, "System4/root"),
    (SystemType.POLICY, "System5/root"),
]
