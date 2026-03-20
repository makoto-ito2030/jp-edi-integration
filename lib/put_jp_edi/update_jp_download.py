"""lib/put_jp_edi/update_jp_download.py - Update goods_hawb_ext.jp_download after PUT."""

import logging
from typing import List

from lib.clients.db_client import DBClient

logger = logging.getLogger(__name__)


def update_jp_download(hawb_nos: List[str]) -> None:
    """
    Set jp_download = 1 for each hawb_no.
    INSERT if record does not exist, UPDATE if it does.
    """
    if not hawb_nos:
        return

    sql_check  = "SELECT hawb_no FROM goods_hawb_ext WHERE hawb_no = %s"
    sql_insert = """
        INSERT INTO goods_hawb_ext (hawb_no, jp_download, create_time, update_time)
        VALUES (%s, 1, NOW(), NOW())
    """
    sql_update = """
        UPDATE goods_hawb_ext
        SET jp_download = 1, update_time = NOW()
        WHERE hawb_no = %s
    """

    with DBClient() as db:
        for hawb_no in hawb_nos:
            exists = db.execute(sql_check, (hawb_no,))
            if exists:
                db.execute(sql_update, (hawb_no,))
                logger.debug("Updated jp_download: %s", hawb_no)
            else:
                db.execute(sql_insert, (hawb_no,))
                logger.debug("Inserted jp_download: %s", hawb_no)

    logger.info("jp_download updated: %d record(s).", len(hawb_nos))
