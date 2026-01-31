import logging
from pathlib import Path

from src.logging_utils import configure_autogen_logging


def _has_file_handler(logger: logging.Logger, log_path: Path) -> bool:
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            if Path(handler.baseFilename) == log_path:
                return True
    return False


def test_configure_autogen_logging_creates_file_and_handler(tmp_path):
    log_path = configure_autogen_logging(str(tmp_path), filename="runtime_test.log")

    log_file = Path(log_path)
    assert log_file.exists()
    assert _has_file_handler(logging.getLogger(), log_file)


def test_configure_autogen_logging_sets_autogen_levels(tmp_path):
    configure_autogen_logging(str(tmp_path), filename="runtime_levels.log")

    assert logging.getLogger("autogen_core").level == logging.DEBUG
    assert logging.getLogger("autogen_agentchat").level == logging.DEBUG
    assert logging.getLogger("autogen_ext").level == logging.DEBUG
