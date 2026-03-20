"""lib/get_jp_track/fetch_csv.py - Fetch tracking CSV from JP server via SFTP."""

import logging
from pathlib import Path

from lib.clients.sftp_client import SFTPClient

logger = logging.getLogger(__name__)


def fetch_csv(inbox_dir: Path) -> None:
    """Download all CSV files from JP server to inbox_dir."""
    with SFTPClient() as client:
        files = client.listdir()
        csv_files = [f for f in files if f.endswith(".csv")]
        if not csv_files:
            logger.info("No CSV files on JP server.")
            return
        logger.info("Found %d CSV file(s) on JP server.", len(csv_files))
        for name in csv_files:
            client.get(name, inbox_dir / name)
            logger.info("%s -> get_inbox", name)
