"""lib/lock_manager.py - Lock file management for duplicate execution prevention."""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _now_str() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def acquire_lock(lock_file: Path) -> None:
    """Prevent duplicate execution. Exit if lock file exists."""
    if lock_file.exists():
        logger.critical(
            "Another process is running (lock file exists: %s). Exiting.", lock_file
        )
        sys.exit(1)
    lock_file.write_text(f"{os.getpid()}\n{_now_str()}\n", encoding="utf-8")
    logger.info("Lock acquired: %s", lock_file)


def release_lock(lock_file: Path) -> None:
    if lock_file.exists():
        lock_file.unlink()
        logger.info("Lock released: %s", lock_file)
