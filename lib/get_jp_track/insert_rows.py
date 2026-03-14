"""lib/get_insert_rows.py - Bulk INSERT logic for logistic_track."""

import logging
from typing import List, Set, Tuple

from lib.clients.db_client import DBClient
from lib.get_jp_track.progress_manager import GetProgressManager

logger = logging.getLogger(__name__)

BULK_INSERT_CHUNK_SIZE = 1000


def _fetch_existing_keys(db: DBClient, tracking_nos: List[str]) -> Set[Tuple]:
    """
    Fetch existing (tracking_no, baggage_status, report_date) keys for dedup check.
    Returns a set of tuples (tracking_no, baggage_status, report_date).
    """
    if not tracking_nos:
        return set()
    placeholders = ",".join(["%s"] * len(tracking_nos))
    sql = f"""
        SELECT tracking_no, baggage_status, report_date
        FROM logistic_track
        WHERE tracking_no IN ({placeholders})
    """
    rows = db.execute(sql, tuple(tracking_nos))
    return {
        (r["tracking_no"], r["baggage_status"], str(r["report_date"]))
        for r in rows
    }


def _bulk_insert(db: DBClient, rows: List[Tuple]) -> None:
    """
    Bulk insert rows into logistic_track.
    rows: list of tuple (tracking_no, report_date, shipping_club, baggage_status,
                         store_nm_in_charge, create_time, update_time)
    """
    sql = """
        INSERT INTO logistic_track (
            tracking_no, report_date, shipping_club, baggage_status,
            store_nm_in_charge, create_time, update_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    db.executemany(sql, rows)


def insert_rows(csv_name: str, rows: List[Tuple],
                resume_from: int, pm: GetProgressManager) -> None:
    """Bulk INSERT with 1-by-1 fallback on chunk error."""
    with DBClient() as db:
        processed = resume_from
        inserted  = pm.inserted_rows

        for chunk_start in range(0, len(rows), BULK_INSERT_CHUNK_SIZE):
            chunk = rows[chunk_start:chunk_start + BULK_INSERT_CHUNK_SIZE]

            # Dedup: fetch existing keys for this chunk and filter out duplicates
            # row tuple: (tracking_no, report_date, shipping_club, baggage_status, ...)
            tracking_nos = [r[0] for r in chunk]
            existing_keys = _fetch_existing_keys(db, tracking_nos)
            new_rows = [
                r for r in chunk
                if (r[0], r[3], r[1]) not in existing_keys
            ]
            skipped = len(chunk) - len(new_rows)
            if skipped:
                logger.info("%s chunk: %d duplicate(s) skipped.", csv_name, skipped)

            try:
                # Attempt bulk INSERT for the current chunk (duplicates already excluded)
                if new_rows:
                    _bulk_insert(db, new_rows)
                inserted  += len(new_rows)
                processed += len(chunk)
                pm.update(processed, inserted)
                logger.info(
                    "%s chunk OK: rows %d-%d (%d inserted, %d skipped)",
                    csv_name,
                    resume_from + chunk_start + 1,
                    resume_from + chunk_start + len(chunk),
                    len(new_rows),
                    skipped,
                )
            except Exception:
                # Chunk failed: roll back and retry row by row
                logger.warning(
                    "%s chunk error at rows %d-%d. Falling back to row-by-row.",
                    csv_name,
                    resume_from + chunk_start + 1,
                    resume_from + chunk_start + len(chunk),
                )
                for i, row in enumerate(new_rows):
                    row_no = resume_from + chunk_start + i + 1
                    try:
                        # Insert single row
                        _bulk_insert(db, [row])
                        inserted  += 1
                        processed += 1
                    except Exception as e:
                        # Skip error row and record it in progress file
                        processed += 1
                        tracking_no = row[0] if row else ""
                        pm.add_error_row(row_no, tracking_no, str(e))
                        logger.error(
                            "%s row %d INSERT error (skipped): %s", csv_name, row_no, e
                        )
                # Update progress after processing the entire fallback chunk
                pm.update(processed, inserted)
