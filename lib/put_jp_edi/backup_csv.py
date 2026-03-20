"""lib/put_jp_edi/backup_csv.py - Backup CSV to S3."""

import logging
from pathlib import Path

from lib.clients.s3_client import S3Client

logger = logging.getLogger(__name__)


def backup_csv(backup_dir: Path) -> None:
    """
    Upload CSV files in backup_dir to S3.
    On success: delete local file.
    On failure: leave in backup_dir for retry on next run.
    """
    files = sorted(backup_dir.glob("*.csv"))
    if not files:
        return

    s3 = S3Client("s3")
    for f in files:
        try:
            s3.upload(f)
            f.unlink()
            logger.info("%s backed up to S3 and deleted.", f.name)
        except Exception:
            logger.exception("%s S3 backup failed. Left in put_backup for retry.", f.name)
