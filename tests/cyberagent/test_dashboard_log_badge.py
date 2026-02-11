from __future__ import annotations

from pathlib import Path

from src.cyberagent.ui.dashboard_log_badge import count_warnings_errors


def test_count_warnings_errors_counts_active_session_logs(tmp_path: Path) -> None:
    old_log = tmp_path / "old.log"
    new_log = tmp_path / "new.log"
    pid_file = tmp_path / "cyberagent.pid"

    old_log.write_text(
        "\n".join(
            [
                "2025-01-01 00:00:01.000 WARNING [x] old warn",
                "2025-01-01 00:00:02.000 ERROR [x] old err",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    new_log.write_text(
        "\n".join(
            [
                "2025-01-01 00:00:03.000 INFO [x] info",
                "2025-01-01 00:00:04.000 WARNING [x] new warn",
                "2025-01-01 00:00:05.000 ERROR [x] new err",
                "2025-01-01 00:00:06.000 ERROR [x] new err2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Ensure deterministic mtime ordering and include both logs in session.
    old_log.touch()
    new_log.touch()
    pid_file.touch()
    old_log.touch()
    new_log.touch()

    warnings, errors = count_warnings_errors(tmp_path)
    assert warnings == 2
    assert errors == 3


def test_count_warnings_errors_falls_back_to_latest_log_without_pid(
    tmp_path: Path,
) -> None:
    old_log = tmp_path / "old.log"
    new_log = tmp_path / "new.log"
    old_log.write_text("2025-01-01 00:00:01.000 ERROR [x] old err\n", encoding="utf-8")
    new_log.write_text(
        "2025-01-01 00:00:02.000 WARNING [x] new warn\n",
        encoding="utf-8",
    )
    old_log.touch()
    new_log.touch()

    warnings, errors = count_warnings_errors(tmp_path)
    assert warnings == 1
    assert errors == 0


def test_count_warnings_errors_returns_zero_without_logs(tmp_path: Path) -> None:
    warnings, errors = count_warnings_errors(tmp_path)
    assert warnings == 0
    assert errors == 0
