"""JP EDI - PUT batch for shipping CSV."""

import logging
import shutil
import sys
from pathlib import Path

from lib.clients.s3_client import S3Client
from lib.clients.sftp_client import SFTPClient

BASE_DIR   = Path(__file__).resolve().parent.parent
OUTBOX_DIR = BASE_DIR / "work" / "put_outbox"
ERROR_DIR  = BASE_DIR / "work" / "put_error"
LOG_FILE   = BASE_DIR / "logs" / "put_jp_edi.log"


def init_env() -> None:
    # Create working directories and initialize logger
    for d in (OUTBOX_DIR, ERROR_DIR, LOG_FILE.parent):
        d.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def download_csv_from_s3() -> None:
    # Download CSV files from S3 to put_outbox
    s3 = S3Client("s3_put")
    keys = s3.list_objects()
    csv_keys = [k for k in keys if k.endswith(".csv")]
    if not csv_keys:
        logging.info("No CSV files found in S3.")
        return
    logging.info("Found %d CSV file(s) in S3.", len(csv_keys))
    for key in csv_keys:
        name = key.split("/")[-1]
        s3.download(key, OUTBOX_DIR / name)
        logging.info("%s -> put_outbox", name)


def send_csv_to_jp() -> None:
    # Send all CSV files in put_outbox to JP server via SFTP
    files = sorted(OUTBOX_DIR.glob("*.csv"))
    if not files:
        logging.info("No CSV files to send.")
        return
    logging.info("Found %d CSV file(s) in put_outbox.", len(files))

    with SFTPClient() as client:
        for f in files:
            try:
                client.put(f)
                f.unlink()
                logging.info("%s sent and deleted.", f.name)
            except Exception:
                shutil.move(str(f), ERROR_DIR / f.name)
                logging.exception("%s -> put_error. Exiting.", f.name)
                sys.exit(1)


if __name__ == "__main__":
    init_env()
    # Step 1: Download CSV files from S3 to put_outbox
    download_csv_from_s3()
    # Step 2: Send CSV files to JP server via SFTP
    send_csv_to_jp()
