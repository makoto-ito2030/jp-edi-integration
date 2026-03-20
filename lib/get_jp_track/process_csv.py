"""lib/get_jp_track/process_csv.py - Process a single tracking CSV file."""

import logging
from pathlib import Path
from typing import Callable, Optional

from lib.clients.s3_client import S3Client
from lib.get_jp_track.check_track_csv import validate_file
from lib.get_jp_track.parse_track_csv import parse_csv
from lib.get_jp_track.progress_manager import GetProgressManager
from lib.get_jp_track.insert_rows import insert_rows

logger = logging.getLogger(__name__)


def process_csv(
    f: Path,
    s3_backup_enabled: bool,
    on_format_error: Optional[Callable[[str, Exception], None]] = None,
    on_complete_with_error: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Process a single tracking CSV file.

    Args:
        f: Path to the CSV file in get_inbox.
        s3_backup_enabled: Whether to upload to S3.
        on_format_error: Callback called on format check failure. Args: (filename, error)
        on_complete_with_error: Callback called when completed with errors. Args: (filename)
    """
    logger.info("--- Processing: %s ---", f.name)
    pm = GetProgressManager(f.name)

    # [1] Initialize or resume progress file immediately
    if pm.load():
        resume_from = pm.processed_rows
        logger.info("%s resuming from row %d.", f.name, resume_from + 1)
    else:
        resume_from = 0
        pm.init()
        logger.info("%s progress file created.", f.name)

    # [2] Back up the raw CSV to S3
    if s3_backup_enabled:
        s3 = S3Client("s3_get")
        s3_backup = "ok"
        try:
            uri = s3.upload(f)
            logger.info("%s S3 backup OK: %s", f.name, uri)
        except Exception:
            s3_backup = "ng"
            logger.warning("%s S3 backup failed. Continuing.", f.name)
        pm.set_s3_backup(s3_backup)
    else:
        logger.info("%s S3 backup skipped (disabled).", f.name)

    # [3] Validate CSV format (column count, required fields, datetime format)
    try:
        validate_file(f)
        pm.set_format_check("ok")
        logger.info("%s format OK", f.name)
    except ValueError as e:
        pm.set_format_check("ng", str(e))
        logger.error("%s format NG (left in get_inbox for retry): %s", f.name, e)
        if on_format_error:
            on_format_error(f.name, e)
        return

    # [4] Parse CSV into DB row tuples
    rows = parse_csv(f)
    total_rows = len(rows)
    logger.info("%s parsed: %d rows", f.name, total_rows)
    pm.set_total_rows(total_rows)

    # [5] Slice rows for resume
    if resume_from:
        rows = rows[resume_from:]

    # [6] Insert rows into DB (bulk INSERT with row-by-row fallback on error)
    insert_rows(f.name, rows, resume_from, pm)

    # [7] Delete progress file if all OK, otherwise leave for manual action
    all_ok = pm.finalize()

    # [8] Remove CSV from get_inbox only if all OK (original is preserved in S3)
    if all_ok:
        f.unlink(missing_ok=True)
        logger.info("%s deleted from get_inbox.", f.name)
    else:
        logger.warning("%s left in get_inbox for manual action.", f.name)
        if on_complete_with_error:
            on_complete_with_error(f.name)
