"""JP EDI - GET batch for tracking CSV."""

import logging
from datetime import datetime
from pathlib import Path

from lib.clients.sftp_client import SFTPClient
from lib.clients.s3_client import S3Client
from lib.get_check_track_csv import validate_file
from lib.get_parse_track_csv import parse_csv
from lib.lock_manager import acquire_lock, release_lock
from lib.get_progress_manager import GetProgressManager
from lib.get_insert_rows import insert_rows

BASE_DIR     = Path(__file__).resolve().parent.parent
INBOX_DIR    = BASE_DIR / "work" / "get_inbox"
LOCK_FILE    = BASE_DIR / "work" / "get_jp_track.lock"
LOG_FILE     = BASE_DIR / "logs" / f"get_jp_track_{datetime.now().strftime('%Y%m')}.log"


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


def get_csv_from_jp() -> None:
    # Connect to JP server via SFTP and download all CSV files to get_inbox
    with SFTPClient() as client:
        files = client.listdir()
        csv_files = [f for f in files if f.endswith(".csv")]
        if not csv_files:
            logging.info("No CSV files on JP server.")
            return
        logging.info("Found %d CSV file(s) on JP server.", len(csv_files))
        for name in csv_files:
            client.get(name, INBOX_DIR / name)
            logging.info("%s -> get_inbox", name)


def process_csv_files() -> None:
    # Process each CSV file in get_inbox sequentially
    files = sorted(INBOX_DIR.glob("*.csv"))
    if not files:
        logging.info("No CSV files to process.")
        return
    logging.info("Found %d CSV file(s) in get_inbox.", len(files))

    for f in files:
        logging.info("--- Processing: %s ---", f.name)
        pm = GetProgressManager(f.name)

        # [1] Initialize or resume progress file immediately
        if pm.load():
            resume_from = pm.processed_rows
            logging.info("%s resuming from row %d.", f.name, resume_from + 1)
        else:
            resume_from = 0
            pm.init()
            logging.info("%s progress file created.", f.name)

        # [2] Back up the raw CSV to S3
        s3 = S3Client("s3_get")
        if s3.enabled:
            s3_backup = "ok"
            try:
                uri = s3.upload(f)
                logging.info("%s S3 backup OK: %s", f.name, uri)
            except Exception:
                s3_backup = "ng"
                logging.warning("%s S3 backup failed. Continuing.", f.name)
            pm.set_s3_backup(s3_backup)
        else:
            logging.info("%s S3 backup skipped (disabled).", f.name)

        # [3] Validate CSV format (column count, required fields, datetime format)
        try:
            validate_file(f)
            pm.set_format_check("ok")
            logging.info("%s format OK", f.name)
        except ValueError as e:
            # Record format error in progress file and leave CSV in get_inbox for retry
            pm.set_format_check("ng", str(e))
            logging.error("%s format NG (left in get_inbox for retry): %s", f.name, e)
            continue

        # [4] Parse CSV into DB row tuples
        rows = parse_csv(f)
        total_rows = len(rows)
        logging.info("%s parsed: %d rows", f.name, total_rows)
        pm.set_total_rows(total_rows)

        # [5] Slice rows for resume
        if resume_from:
            rows = rows[resume_from:]

        # [6] Insert rows into DB (bulk INSERT with row-by-row fallback on error)
        insert_rows(f.name, rows, resume_from, pm)

        # [7] Delete progress file if all OK, otherwise leave for manual action
        pm.finalize()

        # [8] Remove CSV from get_inbox (original is preserved in S3)
        f.unlink(missing_ok=True)
        logging.info("%s deleted from get_inbox.", f.name)



if __name__ == "__main__":
    init_env()
    # Prevent duplicate execution with lock file
    acquire_lock(LOCK_FILE)
    try:
        # Step 1: Download CSV files from JP server via SFTP
        get_csv_from_jp()
        # Step 2: Validate, parse, and insert each CSV into the DB
        process_csv_files()
    finally:
        # Always release lock on exit (normal or abnormal)
        release_lock(LOCK_FILE)
