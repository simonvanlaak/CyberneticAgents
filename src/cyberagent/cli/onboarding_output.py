from __future__ import annotations

from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from src.cyberagent.cli.message_catalog import get_message
from src.cyberagent.db.init_db import get_database_path, recover_sqlite_database
from src.cyberagent.db.session_context import managed_session
from src.cyberagent.db.models.strategy import Strategy
from src.cyberagent.services import purposes as purposes_service
from src.cyberagent.services import strategies as strategies_service


def build_onboarding_prompt(summary_path: Path, summary_text: str) -> str:
    from src.cyberagent.cli.onboarding_discovery import build_onboarding_prompt

    return build_onboarding_prompt(summary_path=summary_path, summary_text=summary_text)


def apply_onboarding_output(
    *,
    team_id: int,
    summary_path: Path | str,
    onboarding_strategy_name: str,
) -> None:
    """Apply onboarding discovery output to root context."""

    if isinstance(summary_path, str):
        summary_path = Path(summary_path)

    if not summary_path.exists():
        return
    try:
        summary_text = summary_path.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if not summary_text:
        return

    # Update purpose (System5 root context). Keep any default purpose content and
    # append the onboarding output for traceability.
    purpose = purposes_service.get_or_create_default_purpose(team_id)
    existing = (purpose.content or "").strip()
    if summary_text in existing:
        purpose_block = existing
    elif not existing:
        purpose_block = summary_text
    else:
        purpose_block = "\n\n".join(
            [
                existing,
                "---",
                "# Onboarding Output",
                f"(Source: {summary_path})",
                "",
                summary_text,
            ]
        )
    try:
        purposes_service.update_purpose_fields(purpose, content=purpose_block)
    except SQLAlchemyError as exc:
        print_db_write_error("purpose", exc)
        return

    # Ensure an initial strategy exists and attach the onboarding output.
    try:
        with managed_session() as session:
            strategy = (
                session.query(Strategy)
                .filter(
                    Strategy.team_id == team_id,
                    Strategy.name == onboarding_strategy_name,
                )
                .first()
            )
            if strategy is None:
                strategy = strategies_service.create_strategy(
                    team_id=team_id,
                    purpose_id=purpose.id,
                    name=onboarding_strategy_name,
                    description=summary_text,
                )
            else:
                existing_desc = (strategy.description or "").strip()
                if summary_text not in existing_desc:
                    strategy.description = (
                        summary_text
                        if not existing_desc
                        else "\n\n".join(
                            [
                                existing_desc,
                                "---",
                                "# Onboarding Output",
                                f"(Source: {summary_path})",
                                "",
                                summary_text,
                            ]
                        )
                    )
                    session.add(strategy)
                    session.commit()
    except SQLAlchemyError as exc:
        print_db_write_error("strategy", exc)


def print_db_write_error(context: str, exc: SQLAlchemyError) -> None:
    db_path = get_database_path()
    message = str(exc).lower()
    hint = get_message("onboarding", "db_write_hint_default")
    if "disk i/o" in message:
        backup_path = recover_sqlite_database()
        if backup_path is not None:
            print(
                get_message(
                    "onboarding",
                    "db_recovered_hint",
                    backup_path=backup_path,
                )
            )
        hint = get_message("onboarding", "db_write_hint_disk_io")
    location = "in-memory database" if db_path == ":memory:" else db_path
    print(
        get_message(
            "onboarding",
            "db_write_failed",
            context=context,
            location=location,
        )
    )
    print(get_message("onboarding", "db_write_hint", hint=hint))
