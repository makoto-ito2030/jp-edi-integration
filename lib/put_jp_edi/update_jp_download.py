"""lib/put_jp_edi/update_jp_download.py - Update goods_hawb_ext.jp_download after PUT."""

import logging
from typing import List

from lib.clients.db_client import DBClient

logger = logging.getLogger(__name__)


CHUNK_SIZE = 10000


def _update_chunk(db: DBClient, chunk: List[str]) -> None:
    """SELECT existing → bulk INSERT new / bulk UPDATE existing."""
    placeholders = ",".join(["%s"] * len(chunk))
    params = tuple(chunk)

    # [1] Find which hawb_nos already exist
    sql_select = f"SELECT hawb_no FROM goods_hawb_ext WHERE hawb_no IN ({placeholders})"
    existing = {row["hawb_no"] for row in db.execute(sql_select, params)}

    new_hawb_nos      = [h for h in chunk if h not in existing]
    existing_hawb_nos = [h for h in chunk if h in existing]

    # [2] Bulk INSERT new records
    if new_hawb_nos:
        insert_placeholders = ",".join(["(%s, 1, NOW(), NOW())"] * len(new_hawb_nos))
        db.execute(
            f"INSERT INTO goods_hawb_ext (hawb_no, jp_download, create_time, update_time) "
            f"VALUES {insert_placeholders}",
            tuple(new_hawb_nos),
        )
        logger.info("jp_download inserted: %d new record(s).", len(new_hawb_nos))

    # [3] Bulk UPDATE existing records
    if existing_hawb_nos:
        update_placeholders = ",".join(["%s"] * len(existing_hawb_nos))
        db.execute(
            f"UPDATE goods_hawb_ext SET jp_download = 1, update_time = NOW() "
            f"WHERE hawb_no IN ({update_placeholders})",
            tuple(existing_hawb_nos),
        )
        logger.info("jp_download updated: %d existing record(s).", len(existing_hawb_nos))


def update_jp_download(hawb_nos: List[str]) -> None:
    """
    Set jp_download = 1 for each hawb_no.
    Processes in chunks of CHUNK_SIZE.
    1. SELECT existing records first.
    2. Bulk INSERT new records.
    3. Bulk UPDATE existing records.
    hawb_no has no UNIQUE constraint, so ON DUPLICATE KEY UPDATE cannot be used.
    """
    if not hawb_nos:
        return

    with DBClient() as db:
        for i in range(0, len(hawb_nos), CHUNK_SIZE):
            chunk = hawb_nos[i:i + CHUNK_SIZE]
            _update_chunk(db, chunk)
            logger.info(
                "jp_download chunk processed: %d-%d / %d",
                i + 1, i + len(chunk), len(hawb_nos),
            )

    logger.info("jp_download updated: %d record(s) total.", len(hawb_nos))
