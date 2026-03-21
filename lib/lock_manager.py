"""lib/lock_manager.py - Lock file management for duplicate execution prevention."""

import logging
import os
from datetime import datetime
from pathlib import Path

from lib.exceptions import LockError

logger = logging.getLogger(__name__)


def _now_str() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


class LockManager:
    """Context manager for lock file based duplicate execution prevention.

    Usage:
        with LockManager(LOCK_FILE):
            # do work

    Raises LockError on __enter__ if lock file already exists.
    Releases lock on __exit__ only if lock was successfully acquired.
    """

    def __init__(self, lock_file: Path) -> None:
        self._lock_file = lock_file
        self._acquired = False

    def __enter__(self) -> "LockManager":
        if self._lock_file.exists():
            logger.critical(
                "Another process is running (lock file exists: %s). Exiting.", self._lock_file
            )
            raise LockError(f"Lock file already exists: {self._lock_file}")
        self._lock_file.write_text(f"{os.getpid()}\n{_now_str()}\n", encoding="utf-8")
        self._acquired = True
        logger.info("Lock acquired: %s", self._lock_file)
        return self

    def __exit__(self, *_) -> None:
        if self._acquired and self._lock_file.exists():
            self._lock_file.unlink()
            logger.info("Lock released: %s", self._lock_file)
