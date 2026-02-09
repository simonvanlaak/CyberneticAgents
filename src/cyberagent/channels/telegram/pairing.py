from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import os
from pathlib import Path
import secrets
from typing import Iterable

from sqlalchemy.orm import Session

from src.cyberagent.channels.telegram.outbound import (
    send_message as send_telegram_message,
    send_message_with_inline_keyboard,
)
from src.cyberagent.channels.telegram.parser import parse_allowlist
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.telegram_pairing import TelegramPairing
from src.cyberagent.secrets import get_secret, store_secret_in_1password

PAIRING_STATUS_PENDING = "pending"
PAIRING_STATUS_APPROVED = "approved"
PAIRING_STATUS_DENIED = "denied"

PAIRING_ADMIN_SECRET = "TELEGRAM_PAIRING_ADMIN_CHAT_IDS"

PAIRING_CALLBACK_PREFIX = "pairing"
PAIRING_CALLBACK_APPROVE = "approve"
PAIRING_CALLBACK_DENY = "deny"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PairingCallback:
    action: str
    code: str


def is_pairing_enabled() -> bool:
    raw = os.environ.get("TELEGRAM_PAIRING_ENABLED", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def load_admin_chat_ids() -> set[int]:
    raw = os.environ.get(PAIRING_ADMIN_SECRET)
    if not raw:
        raw = get_secret(PAIRING_ADMIN_SECRET)
    return parse_allowlist(raw)


def is_admin_chat(chat_id: int) -> bool:
    admin_ids = load_admin_chat_ids()
    return chat_id in admin_ids if admin_ids else False


def has_admin_chat_ids() -> bool:
    return bool(load_admin_chat_ids())


def store_admin_chat_ids(admin_ids: set[int]) -> bool:
    serialized = ",".join(str(entry) for entry in sorted(admin_ids))
    if not serialized:
        return False
    stored = store_secret_in_1password(PAIRING_ADMIN_SECRET, serialized)
    os.environ[PAIRING_ADMIN_SECRET] = serialized
    if not stored:
        _persist_admin_ids_to_env_file(serialized)
        logger.warning("Failed to store Telegram admin chat ids in 1Password.")
    return stored


def _persist_admin_ids_to_env_file(serialized: str) -> None:
    env_path = _find_env_file(Path.cwd()) or (Path.cwd() / ".env")
    lines: list[str] = []
    if env_path.exists():
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return

    prefix = f"{PAIRING_ADMIN_SECRET}="
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{PAIRING_ADMIN_SECRET}={serialized}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{PAIRING_ADMIN_SECRET}={serialized}")
    try:
        env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    except OSError:
        return


def _find_env_file(start: Path) -> Path | None:
    for path in [start, *start.parents]:
        candidate = path / ".env"
        if candidate.exists():
            return candidate
    return None


def bootstrap_admin(
    *,
    chat_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> TelegramPairing:
    store_admin_chat_ids({chat_id})
    record = ensure_admin_pairing_approved(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    return record


def ensure_pairing(
    *,
    chat_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> tuple[TelegramPairing, bool]:
    session = next(get_db())
    try:
        record = (
            session.query(TelegramPairing)
            .filter(
                TelegramPairing.chat_id == chat_id,
                TelegramPairing.user_id == user_id,
            )
            .one_or_none()
        )
        now = datetime.utcnow()
        if record is None:
            code = _generate_unique_code(session)
            record = TelegramPairing(
                chat_id=chat_id,
                user_id=user_id,
                status=PAIRING_STATUS_PENDING,
                pairing_code=code,
                username=username,
                first_name=first_name,
                last_name=last_name,
                created_at=now,
                updated_at=now,
                last_seen_at=now,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record, True
        record.username = username
        record.first_name = first_name
        record.last_name = last_name
        record.last_seen_at = now
        record.updated_at = now
        session.commit()
        session.refresh(record)
        return record, False
    finally:
        session.close()


def list_pairings(status: str | None = None) -> list[TelegramPairing]:
    session = next(get_db())
    try:
        query = session.query(TelegramPairing)
        if status:
            query = query.filter(TelegramPairing.status == status)
        return list(query.order_by(TelegramPairing.last_seen_at.desc()))
    finally:
        session.close()


def get_pairing_by_code(code: str) -> TelegramPairing | None:
    session = next(get_db())
    try:
        return (
            session.query(TelegramPairing)
            .filter(TelegramPairing.pairing_code == code)
            .one_or_none()
        )
    finally:
        session.close()


def approve_pairing(code: str, admin_chat_id: int | None) -> TelegramPairing | None:
    return _update_pairing_status(code, PAIRING_STATUS_APPROVED, admin_chat_id)


def deny_pairing(code: str, admin_chat_id: int | None) -> TelegramPairing | None:
    return _update_pairing_status(code, PAIRING_STATUS_DENIED, admin_chat_id)


def parse_pairing_callback(data: str | None) -> PairingCallback | None:
    if not data:
        return None
    parts = data.split(":", 2)
    if len(parts) != 3:
        return None
    prefix, action, code = parts
    if prefix != PAIRING_CALLBACK_PREFIX:
        return None
    if action not in {PAIRING_CALLBACK_APPROVE, PAIRING_CALLBACK_DENY}:
        return None
    if not code:
        return None
    return PairingCallback(action=action, code=code)


def user_prompt_for_status(record: TelegramPairing) -> str:
    if record.status == PAIRING_STATUS_DENIED:
        return "Not authorized. Contact an admin to request access."
    return (
        "Pairing required. Share this code with an admin to approve: "
        f"{record.pairing_code}"
    )


def admin_notification_text(record: TelegramPairing) -> str:
    user_bits = _format_user_info(record)
    return (
        "Telegram pairing request received.\n"
        f"Code: {record.pairing_code}\n"
        f"User: {user_bits}\n"
        f"Chat ID: {record.chat_id}\n"
        f"User ID: {record.user_id}"
    )


def notify_admins(record: TelegramPairing) -> int:
    admin_ids = load_admin_chat_ids()
    if not admin_ids:
        return 0
    text = admin_notification_text(record)
    buttons = [
        (
            "Approve",
            f"{PAIRING_CALLBACK_PREFIX}:{PAIRING_CALLBACK_APPROVE}:{record.pairing_code}",
        ),
        (
            "Deny",
            f"{PAIRING_CALLBACK_PREFIX}:{PAIRING_CALLBACK_DENY}:{record.pairing_code}",
        ),
    ]
    _broadcast_with_inline_buttons(admin_ids, text, buttons)
    return len(admin_ids)


def notify_user_approved(record: TelegramPairing) -> None:
    send_telegram_message(
        record.chat_id, "Your Telegram pairing request was approved. You can chat now."
    )


def notify_user_denied(record: TelegramPairing) -> None:
    send_telegram_message(
        record.chat_id,
        "Your Telegram pairing request was denied. Contact an admin if this is unexpected.",
    )


def ensure_admin_pairing_approved(
    *,
    chat_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> TelegramPairing:
    record, _created = ensure_pairing(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    if record.status != PAIRING_STATUS_APPROVED:
        updated = approve_pairing(record.pairing_code, admin_chat_id=chat_id)
        if updated is not None:
            return updated
    return record


def _update_pairing_status(
    code: str, status: str, admin_chat_id: int | None
) -> TelegramPairing | None:
    session = next(get_db())
    try:
        record = (
            session.query(TelegramPairing)
            .filter(TelegramPairing.pairing_code == code)
            .one_or_none()
        )
        if record is None:
            return None
        now = datetime.utcnow()
        record.status = status
        record.updated_at = now
        record.last_seen_at = now
        if status == PAIRING_STATUS_APPROVED:
            record.approved_by_chat_id = admin_chat_id
            record.approved_at = now
        if status == PAIRING_STATUS_DENIED:
            record.denied_by_chat_id = admin_chat_id
            record.denied_at = now
        session.commit()
        session.refresh(record)
        return record
    finally:
        session.close()


def _format_user_info(record: TelegramPairing) -> str:
    parts: list[str] = []
    if record.username:
        parts.append(f"@{record.username}")
    name_bits = " ".join(part for part in [record.first_name, record.last_name] if part)
    if name_bits:
        parts.append(name_bits)
    if not parts:
        return "Unknown user"
    return " / ".join(parts)


def _generate_unique_code(session: Session) -> str:
    for _ in range(10):
        code = secrets.token_hex(3).upper()
        exists = (
            session.query(TelegramPairing)
            .filter(TelegramPairing.pairing_code == code)
            .count()
        )
        if not exists:
            return code
    raise RuntimeError("Failed to generate unique Telegram pairing code.")


def _broadcast_with_inline_buttons(
    admin_ids: Iterable[int], text: str, buttons: list[tuple[str, str]]
) -> None:
    for chat_id in admin_ids:
        send_message_with_inline_keyboard(chat_id, text, buttons)
