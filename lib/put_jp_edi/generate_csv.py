"""lib/put_jp_edi/generate_csv.py - Generate DENFD CSV from goods_hawb."""

import configparser
import csv
import logging
from lib.exceptions import ConfigError
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lib.clients.db_client import DBClient
from lib.put_jp_edi.sanitize import sanitize

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "settings.ini"

# Size code mapping: upper bound (cm) -> code
_SIZE_THRESHOLDS = [
    (60,  "060"),
    (80,  "080"),
    (100, "100"),
    (120, "120"),
    (140, "140"),
    (160, "160"),
    (170, "170"),
]


def _load_jp_edi_config() -> dict:
    if not CONFIG_PATH.exists():
        logger.critical("settings.ini not found: %s", CONFIG_PATH)
        raise ConfigError(f"Configuration error: see log for details")
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")
    if "jp_edi" not in config:
        logger.critical("Missing [jp_edi] section in %s", CONFIG_PATH)
        raise ConfigError(f"Configuration error: see log for details")
    jp = config["jp_edi"]
    return {
        "biz_card_no":            jp["biz_card_no"],
        "shipper_name":           jp["shipper_name"],
        "shipper_tel":            jp.get("shipper_tel", ""),
        "shipper_postal_code":    jp.get("shipper_postal_code", ""),
        "shipper_address":        jp.get("shipper_address", ""),
        "tracking_no_prefix":     jp.get("tracking_no_prefix", ""),
        "put_filename_template":  jp["put_filename_template"],
    }


def _resolve_size_code(length, width, height) -> Optional[str]:
    """
    Calculate size code from 3 dimensions (cm).
    Returns size code string, or None if dimensions are missing/invalid.
    """
    try:
        l, w, h = int(length or 0), int(width or 0), int(height or 0)
    except (TypeError, ValueError):
        return None
    if l == 0 and w == 0 and h == 0:
        return None
    total = l + w + h
    for threshold, code in _SIZE_THRESHOLDS:
        if total <= threshold:
            return code
    return "170"  # over 170cm: use max size code


def _fetch_rows(db: DBClient, tracking_no_prefix: str) -> List[Dict]:
    """Fetch target records from goods_hawb."""
    sql = """
        SELECT g.*
        FROM goods_hawb g
        LEFT JOIN goods_hawb_ext e ON g.hawb_no = e.hawb_no
        WHERE (
            (g.tracking_no LIKE %s)
            OR (g.tracking_no IS NULL AND g.shipping_club = 'Yu-Pack')
        )
        AND g.customs_permit_time IS NOT NULL
        AND g.move_out_time IS NOT NULL
        AND g.is_delete = 0
        AND (
            e.jp_download IS NULL
            OR e.jp_download = 0
        )
        ORDER BY g.id ASC
    """
    return db.execute(sql, (f"{tracking_no_prefix}%",))


def _build_row(row: Dict, conf: dict, size_warnings: List[str]) -> Optional[List[str]]:
    """
    Build a single DENFD CSV row (50 fields) from a goods_hawb record.
    Returns None if size code cannot be resolved (record is skipped).
    """
    s = sanitize
    blank = ""

    size_code = _resolve_size_code(row.get("length"), row.get("width"), row.get("height"))
    if size_code is None:
        size_warnings.append(
            f"hawb_no={row.get('hawb_no')} "
            f"length={row.get('length')} width={row.get('width')} height={row.get('height')}"
        )
        return None

    return [
        "DENKAKUTEI",                                            # 1
        blank,                                                   # 2
        blank,                                                   # 3
        "101",                                                   # 4
        blank,                                                   # 5
        blank,                                                   # 6
        s(row.get("tracking_no") or blank),                      # 7
        s(row.get("hawb_no") or blank),                          # 8
        blank,                                                   # 9
        conf["biz_card_no"],                                     # 10
        conf["shipper_name"],                                    # 11
        conf["shipper_tel"],                                     # 12
        conf["shipper_postal_code"],                             # 13
        conf["shipper_address"],                                 # 14
        s(row.get("consignee_name") or blank),                   # 15
        s(row.get("consignee_tel") or blank),                    # 16
        s(row.get("consignee_postal_code") or blank),            # 17
        s(row.get("consignee_address_full") or blank),           # 18
        blank,                                                   # 19
        blank,                                                   # 20
        blank,                                                   # 21
        blank,                                                   # 22
        blank,                                                   # 23
        blank,                                                   # 24
        blank,                                                   # 25
        blank,                                                   # 26
        size_code,                                               # 27
        blank,                                                   # 28
        blank,                                                   # 29
        blank,                                                   # 30
        blank,                                                   # 31
        "0",                                                     # 32
        "0",                                                     # 33
        "0",                                                     # 34
        "0",                                                     # 35
        blank,                                                   # 36
        blank,                                                   # 37
        blank,                                                   # 38
        blank,                                                   # 39
        blank,                                                   # 40
        blank,                                                   # 41
        blank,                                                   # 42
        blank,                                                   # 43
        blank,                                                   # 44
        blank,                                                   # 45
        blank,                                                   # 46
        blank,                                                   # 47
        blank,                                                   # 48
        blank,                                                   # 49
        blank,                                                   # 50
    ]


def generate_csv(outbox_dir: Path) -> Optional[Tuple[Path, List[str], List[str]]]:
    """
    Fetch records from DB and generate DENFD CSV in outbox_dir.
    Returns (output file path, list of hawb_no, list of size warning messages),
    or None if no records found.
    """
    conf = _load_jp_edi_config()
    filename = conf["put_filename_template"].replace(
        "0000000000000", datetime.now().strftime("%Y%m%d%H%M%S")
    )
    output_path = outbox_dir / filename

    with DBClient() as db:
        rows = _fetch_rows(db, conf["tracking_no_prefix"])

    if not rows:
        logger.info("No records to export.")
        return None

    logger.info("Fetched %d record(s) from DB.", len(rows))

    size_warnings: List[str] = []
    exported_rows: List[Dict] = []
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\r\n")
        for row in rows:
            csv_row = _build_row(row, conf, size_warnings)
            if csv_row is None:
                logger.warning(
                    "Skipped (size unresolvable): hawb_no=%s", row.get("hawb_no")
                )
                continue
            writer.writerow(csv_row)
            exported_rows.append(row)

    if size_warnings:
        logger.warning(
            "%d record(s) skipped due to missing size info.", len(size_warnings)
        )

    if not exported_rows:
        output_path.unlink(missing_ok=True)
        logger.info("No records exported after skipping size NG rows.")
        return None

    logger.info(
        "Generated CSV: %s (%d rows, %d skipped)",
        output_path.name, len(exported_rows), len(size_warnings)
    )

    hawb_nos = [row["hawb_no"] for row in exported_rows if row.get("hawb_no")]
    return output_path, hawb_nos, size_warnings
