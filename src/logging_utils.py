import logging
import os
import time
from pathlib import Path


def configure_autogen_logging(
    logs_dir: str, filename: str | None = None, level: int = logging.DEBUG
) -> str:
    """
    Configure Python logging to capture AutoGen runtime logs into a file.

    Args:
        logs_dir: Directory to write the log file into.
        filename: Optional fixed filename for determinism in tests.
        level: Logging level to apply to root and autogen loggers.

    Returns:
        Absolute path to the configured log file.
    """
    os.makedirs(logs_dir, exist_ok=True)
    if filename is None:
        filename = time.strftime("runtime_%Y%m%d_%H%M%S.log")
    log_path = Path(logs_dir) / filename
    log_path.touch(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    normalized_path = str(log_path.resolve())
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            if os.path.abspath(handler.baseFilename) == normalized_path:
                return normalized_path

    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(normalized_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    for logger_name in ("autogen_core", "autogen_agentchat", "autogen_ext"):
        logging.getLogger(logger_name).setLevel(level)

    return normalized_path
