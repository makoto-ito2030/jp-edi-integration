"""JP EDI - GET batch for tracking CSV."""

import configparser
import logging
import traceback
from datetime import datetime
from pathlib import Path

from lib.lock_manager import acquire_lock, release_lock
from lib.mail_client import send_error_mail
from lib.get_jp_track.fetch_csv import fetch_csv
from lib.get_jp_track.process_csv import process_csv

BASE_DIR     = Path(__file__).resolve().parent.parent
CONFIG_PATH  = BASE_DIR / "config" / "settings.ini"
INBOX_DIR    = BASE_DIR / "work" / "get_inbox"
LOCK_FILE    = BASE_DIR / "work" / "get_jp_track.lock"
LOG_FILE     = BASE_DIR / "logs" / f"get_jp_track_{datetime.now().strftime('%Y%m')}.log"

_config = configparser.ConfigParser()
_config.read(CONFIG_PATH, encoding="utf-8")
S3_BACKUP_ENABLED = _config.getboolean("feature", "s3_backup_enabled", fallback=True)
SFTP_GET_ENABLED  = _config.getboolean("feature", "sftp_get_enabled",  fallback=True)
MAIL_ENABLED      = _config.getboolean("feature", "mail_enabled",      fallback=True)


def init_env() -> None:
    # Create working directories and initialize logger
    for d in (INBOX_DIR, LOG_FILE.parent):
        d.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def _on_format_error(filename: str, error: Exception) -> None:
    if MAIL_ENABLED:
        send_error_mail(
            subject=f"[ERROR] get_jp_track: format error in {filename}",
            body=f"Format check failed.\n\nFile: {filename}\nError: {error}",
        )


def _on_complete_with_error(filename: str) -> None:
    if MAIL_ENABLED:
        send_error_mail(
            subject=f"[ERROR] get_jp_track: processing error in {filename}",
            body=f"Processing completed with errors. Manual action required.\n\nFile: {filename}\nProgress file: work/get_progress/{filename}.progress.json",
        )


def step1_prevent_duplicate_execution() -> None:
    """Prevent duplicate execution using a lock file."""
    acquire_lock(LOCK_FILE)


def step2_fetch_csv() -> None:
    """Fetch tracking CSV files from JP server via SFTP and save to get_inbox."""
    if SFTP_GET_ENABLED:
        fetch_csv(INBOX_DIR)
    else:
        logging.info("SFTP download skipped (disabled).")


def step3_process_csv_files() -> None:
    """Process each CSV file in get_inbox sequentially.
    For each file:
      - Initialize or resume progress file
      - Back up to S3
      - Validate format
      - Parse, dedup check, and bulk INSERT
      - Clean up on completion
    """
    for f in sorted(INBOX_DIR.glob("*.csv")):
        process_csv(
            f,
            s3_backup_enabled=S3_BACKUP_ENABLED,
            on_format_error=_on_format_error,
            on_complete_with_error=_on_complete_with_error,
        )


if __name__ == "__main__":
    init_env()
    step1_prevent_duplicate_execution()
    try:
        step2_fetch_csv()
        step3_process_csv_files()

    except Exception:
        logging.exception("Batch failed.")
        if MAIL_ENABLED:
            send_error_mail(
                subject="[ERROR] get_jp_track batch failed",
                body=f"An error occurred in get_jp_track batch.\n\n{traceback.format_exc()}",
            )
    finally:
        release_lock(LOCK_FILE)
