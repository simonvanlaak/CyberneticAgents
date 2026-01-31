import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class UiMessage:
    sender: str
    content: str
    is_user: bool
    timestamp: float


_messages: list[UiMessage] = []
_user_notices: list[UiMessage] = []
_log_file_path: str | None = None
_lock = threading.Lock()


def add_message(sender: str, content: str, is_user: bool) -> None:
    with _lock:
        message = UiMessage(
            sender=sender,
            content=content,
            is_user=is_user,
            timestamp=time.time(),
        )
        _messages.append(message)
        _append_log_line(message, is_notice=False)


def add_user_notice(sender: str, content: str) -> None:
    if not content or not content.strip():
        return
    with _lock:
        notice = UiMessage(
            sender=sender,
            content=content,
            is_user=False,
            timestamp=time.time(),
        )
        _user_notices.append(notice)
        _append_log_line(notice, is_notice=True)


def get_messages() -> list[UiMessage]:
    with _lock:
        return list(_messages)


def get_latest_user_notice() -> UiMessage | None:
    with _lock:
        for notice in reversed(_user_notices):
            if notice.content.strip():
                return notice
        return None


def get_log_text() -> str:
    with _lock:
        return "\n".join(f"[{msg.sender}] {msg.content}" for msg in _messages)


def clear_messages() -> None:
    with _lock:
        _messages.clear()
        _user_notices.clear()


def set_log_file(path: str) -> None:
    global _log_file_path
    _log_file_path = path


def _append_log_line(message: UiMessage, is_notice: bool) -> None:
    if _log_file_path is None:
        return
    if message.content.startswith("..."):
        return
    timestamp_struct = time.localtime(message.timestamp)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", timestamp_struct)
    milliseconds = int((message.timestamp - int(message.timestamp)) * 1000)
    prefix = "NOTICE" if is_notice else "MESSAGE"
    line = (
        f"[{timestamp}.{milliseconds:03d}] {prefix} [{message.sender}] "
        f"(is_user={message.is_user} len={len(message.content)} ts={message.timestamp:.6f}) "
        f"{message.content}\n"
    )
    try:
        with open(_log_file_path, "a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass
