"""JP EDI - PUT batch for shipping CSV."""

import configparser
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from lib.lock_manager import LockManager
from lib.log_manager import cleanup_old_logs
from lib.exceptions import LockError, ConfigError
from lib.clients.mail_client import send_error_mail
from lib.put_jp_edi.generate_csv import generate_csv
from lib.put_jp_edi.send_csv import send_csv
from lib.put_jp_edi.update_jp_download import update_jp_download
from lib.put_jp_edi.backup_csv import backup_csv

BASE_DIR    = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "settings.ini"
OUTBOX_DIR  = BASE_DIR / "work" / "put_outbox"
BACKUP_DIR  = BASE_DIR / "work" / "put_backup"
ERROR_DIR   = BASE_DIR / "work" / "put_error"
LOCK_FILE   = BASE_DIR / "work" / "put_jp_edi.lock"
LOG_FILE    = BASE_DIR / "logs" / f"put_jp_edi_{datetime.now().strftime('%Y%m')}.log"

_config = configparser.ConfigParser()
_config.read(CONFIG_PATH, encoding="utf-8")
SFTP_PUT_ENABLED  = _config.getboolean("feature", "sftp_put_enabled",  fallback=True)
S3_BACKUP_ENABLED = _config.getboolean("feature", "s3_backup_enabled", fallback=True)
MAIL_ENABLED      = _config.getboolean("feature", "mail_enabled",      fallback=True)


def init_env() -> None:
    # Create working directories and initialize logger
    for d in (OUTBOX_DIR, BACKUP_DIR, ERROR_DIR, LOG_FILE.parent):
        d.mkdir(parents=True, exist_ok=True)
    cleanup_old_logs(LOG_FILE.parent, "put_jp_edi", _config.getint("feature", "log_keep_months", fallback=7))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def step1_prevent_duplicate_execution() -> LockManager:
    """Prevent duplicate execution using a lock file."""
    return LockManager(LOCK_FILE)


def step2_generate_csv() -> Tuple[Path, List[str], List[str]]:
    """Generate DENFD CSV from DB and place it in put_outbox. Exit if no records."""
    result = generate_csv(OUTBOX_DIR)
    if result is None:
        logging.info("No records to send. Exiting.")
        sys.exit(0)
    return result


def step3_send_csv() -> None:
    """Send CSV in put_outbox to JP server via SFTP. On success, move to put_backup."""
    if SFTP_PUT_ENABLED:
        send_csv(OUTBOX_DIR, BACKUP_DIR, ERROR_DIR)
    else:
        logging.info("SFTP upload skipped (disabled).")


def step4_update_jp_download(hawb_nos: List[str]) -> None:
    """Update goods_hawb_ext.jp_download to 1 for sent records."""
    update_jp_download(hawb_nos)


def step5_backup_csv() -> None:
    """Upload CSV in put_backup to S3. On success, delete local file."""
    if S3_BACKUP_ENABLED:
        backup_csv(BACKUP_DIR)
    else:
        logging.info("S3 backup skipped (disabled).")


def step6_notify_size_warnings(size_warnings: List[str]) -> None:
    """Send a single warning email if any records were skipped due to missing size info."""
    if size_warnings and MAIL_ENABLED:
        send_error_mail(
            subject="[WARN] put_jp_edi: record(s) skipped due to missing size info",
            body=(
                f"{len(size_warnings)} record(s) were skipped because size info "
                f"(length/width/height) is missing or zero.\n"
                "These records were NOT included in the CSV and jp_download was NOT updated.\n"
                "Please set length/width/height in goods_hawb and re-run the batch.\n\n"
                + "\n".join(size_warnings)
            ),
        )


if __name__ == "__main__":
    init_env()
    try:
        with step1_prevent_duplicate_execution():
            csv_path, hawb_nos, size_warnings = step2_generate_csv()
            step3_send_csv()
            step4_update_jp_download(hawb_nos)
            step5_backup_csv()
            step6_notify_size_warnings(size_warnings)

    except LockError:
        logging.critical("Duplicate execution detected. Exiting.")
        if MAIL_ENABLED:
            send_error_mail(
                subject="[ERROR] put_jp_edi: lock file exists",
                body=(
                    "put_jp_edi could not start because the lock file already exists.\n\n"
                    f"Lock file: {LOCK_FILE}\n\n"
                    "If no other process is running, remove the lock file manually and re-run."
                ),
            )
        sys.exit(1)
    except ConfigError:
        logging.critical("Configuration error. Exiting.")
        if MAIL_ENABLED:
            send_error_mail(
                subject="[ERROR] put_jp_edi: configuration error",
                body="put_jp_edi could not start due to a configuration error.\n\nCheck settings.ini and the log for details.",
            )
        sys.exit(1)
    except Exception:
        logging.exception("Batch failed.")
        if MAIL_ENABLED:
            send_error_mail(
                subject="[ERROR] put_jp_edi batch failed",
                body=f"An error occurred in put_jp_edi batch.\n\n{traceback.format_exc()}",
            )
        sys.exit(1)
