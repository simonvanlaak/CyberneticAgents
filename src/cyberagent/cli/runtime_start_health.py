from __future__ import annotations

import time
from typing import Protocol


class SpawnedProcess(Protocol):
    pid: int

    def poll(self) -> int | None: ...


def process_exited_during_startup(
    proc: SpawnedProcess, grace_seconds: float
) -> int | None:
    deadline = time.time() + grace_seconds
    while time.time() < deadline:
        returncode = proc.poll()
        if returncode is not None:
            return returncode
        time.sleep(0.05)
    return proc.poll()
