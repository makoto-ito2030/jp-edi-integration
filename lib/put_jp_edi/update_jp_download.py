"""lib/put_jp_edi/update_jp_download.py - Update goods_hawb_ext.jp_download after PUT."""

import logging
from typing import List

from lib.clients.db_client import DBClient

logger = logging.getLogger(__name__)


CHUNK_SIZE = 1000


def _update_chunk(db: DBClient, chunk: List[str]) -> None:
    """Bulk UPDATE + INSERT for a single chunk of hawb_nos."""
    placeholders = ",".join(["%s"] * len(chunk))
    params = tuple(chunk)

    sql_update = f"""
        UPDATE goods_hawb_ext
        SET jp_download = 1, update_time = NOW()
        WHERE hawb_no IN ({placeholders})
    """
    sql_select_existing = f"""
        SELECT hawb_no FROM goods_hawb_ext
        WHERE hawb_no IN ({placeholders})
    """
    sql_insert = """
        INSERT INTO goods_hawb_ext (hawb_no, jp_download, create_time, update_time)
        VALUES (%s, 1, NOW(), NOW())
    """

    # [1] Bulk UPDATE existing records
    db.execute(sql_update, params)

    # [2] Find hawb_nos that don't exist yet and bulk INSERT them
    existing = {row["hawb_no"] for row in db.execute(sql_select_existing, params)}
    new_hawb_nos = [h for h in chunk if h not in existing]
    if new_hawb_nos:
        db.executemany(sql_insert, [(h,) for h in new_hawb_nos])
        logger.info("jp_download inserted: %d new record(s).", len(new_hawb_nos))


def update_jp_download(hawb_nos: List[str]) -> None:
    """
    Set jp_download = 1 for each hawb_no.
    Processes in chunks of CHUNK_SIZE to avoid max_allowed_packet limits.
    1. Bulk UPDATE existing records via WHERE hawb_no IN (...).
    2. Bulk INSERT only records that do not yet exist.
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
