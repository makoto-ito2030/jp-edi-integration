"""lib/put_jp_edi/send_csv.py - Send CSV to JP server via SFTP."""

import logging
import shutil
from pathlib import Path

from lib.clients.sftp_client import SFTPClient

logger = logging.getLogger(__name__)


def send_csv(outbox_dir: Path, backup_dir: Path, error_dir: Path) -> None:
    """
    Send CSV files in outbox_dir to JP server via SFTP.
    On success: move to backup_dir.
    On failure: move to error_dir and raise.
    """
    files = sorted(outbox_dir.glob("*.csv"))
    if not files:
        logger.info("No CSV files to send.")
        return

    failed = False
    try:
        with SFTPClient() as client:
            for f in files:
                try:
                    client.put(f)
                    shutil.move(str(f), backup_dir / f.name)
                    logger.info("%s sent. Moved to put_backup.", f.name)
                except Exception:
                    shutil.move(str(f), error_dir / f.name)
                    logger.exception("%s -> put_error.", f.name)
                    failed = True
    except Exception:
        # Connection-level failure: move any remaining files in outbox to error_dir
        for f in sorted(outbox_dir.glob("*.csv")):
            shutil.move(str(f), error_dir / f.name)
            logger.error("%s -> put_error (connection failed).", f.name)
        raise

    if failed:
        raise RuntimeError("One or more files failed to send. See log for details.")
