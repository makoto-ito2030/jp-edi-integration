"""lib/put_jp_edi/generate_csv.py - Generate DENFD CSV from goods_hawb."""

import configparser
import csv
import logging
import sys
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
        sys.exit(1)
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")
    if "jp_edi" not in config:
        logger.critical("Missing [jp_edi] section in %s", CONFIG_PATH)
        sys.exit(1)
    jp = config["jp_edi"]
    return {
        "biz_card_no":          jp["biz_card_no"],
        "shipper_name":         jp["shipper_name"],
        "shipper_tel":          jp.get("shipper_tel", ""),
        "shipper_postal_code":  jp.get("shipper_postal_code", ""),
        "shipper_address":      jp.get("shipper_address", ""),
        "tracking_no_prefix":   jp.get("tracking_no_prefix", ""),
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
    return "170"  # 170cm超：最大サイズコードで送信


def _fetch_rows(db: DBClient, tracking_no_prefix: str) -> List[Dict]:
    """Fetch target records from goods_hawb."""
    sql = """
        SELECT g.*
        FROM goods_hawb g
        LEFT JOIN goods_hawb_ext e ON g.hawb_no = e.hawb_no
        WHERE (
            (g.tracking_no LIKE %s)
            OR (g.tracking_no IS NULL AND g.shipping_club = 'ゆうパック')
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


def _build_row(row: Dict, conf: dict, size_warnings: List[str]) -> List[str]:
    """Build a single DENFD CSV row (50 fields) from a goods_hawb record."""
    s = sanitize
    blank = ""

    size_code = _resolve_size_code(row.get("length"), row.get("width"), row.get("height"))
    if size_code is None:
        size_code = blank
        size_warnings.append(
            f"hawb_no={row.get('hawb_no')} "
            f"length={row.get('length')} width={row.get('width')} height={row.get('height')}"
        )

    return [
        "DENKAKUTEI",                                            # 1  予約・確定識別コード
        blank,                                                   # 2  発送(予定)日
        blank,                                                   # 3  発送時刻
        "101",                                                   # 4  商品種別コード（ゆうパック）
        blank,                                                   # 5  注意コード
        blank,                                                   # 6  伝票個数
        s(row.get("tracking_no") or blank),                      # 7  お問い合わせ番号
        s(row.get("hawb_no") or blank),                          # 8  お客様側管理番号
        blank,                                                   # 9  複数個口代表お問い合わせ番号
        conf["biz_card_no"],                                     # 10 ゆうびんビズカードお客さま番号
        conf["shipper_name"],                                    # 11 ご依頼主名
        conf["shipper_tel"],                                     # 12 ご依頼主電話番号
        conf["shipper_postal_code"],                             # 13 ご依頼主郵便番号
        conf["shipper_address"],                                 # 14 ご依頼主住所
        s(row.get("consignee_name") or blank),                   # 15 お届け先名
        s(row.get("consignee_tel") or blank),                    # 16 お届け先電話番号
        s(row.get("consignee_postal_code") or blank),            # 17 お届け先郵便番号
        s(row.get("consignee_address_full") or blank),           # 18 お届け先住所
        blank,                                                   # 19 お届け希望年月日
        blank,                                                   # 20 お届け希望時間帯
        blank,                                                   # 21 代金引換金額
        blank,                                                   # 22 消費税額等
        blank,                                                   # 23 品名１
        blank,                                                   # 24 品名２
        blank,                                                   # 25 品名３
        blank,                                                   # 26 損害要償額
        size_code,                                               # 27 サイズ
        blank,                                                   # 28 記事１
        blank,                                                   # 29 記事２
        blank,                                                   # 30 発送会社コード
        blank,                                                   # 31 発送局コード
        "0",                                                     # 32 配達予告メールサービス
        "0",                                                     # 33 配達完了メールサービス
        "0",                                                     # 34 不在持戻メールサービス
        "0",                                                     # 35 郵便局留めメールサービス
        blank,                                                   # 36 配達予告通知先メールアドレス
        blank,                                                   # 37 配達完了通知先メールアドレス
        blank,                                                   # 38 不在持戻通知先メールアドレス
        blank,                                                   # 39 郵便局留め通知先メールアドレス
        blank,                                                   # 40 配達希望日前倒し
        blank,                                                   # 41 商品表示
        blank,                                                   # 42 自由使用欄
        blank,                                                   # 43 要申込項目
        blank,                                                   # 44 要申込項目
        blank,                                                   # 45 要申込項目
        blank,                                                   # 46 要申込項目
        blank,                                                   # 47 要申込項目
        blank,                                                   # 48 要申込項目
        blank,                                                   # 49 要申込項目
        blank,                                                   # 50 予備
    ]


def generate_csv(outbox_dir: Path) -> Optional[Tuple[Path, List[str], List[str]]]:
    """
    Fetch records from DB and generate DENFD CSV in outbox_dir.
    Returns (output file path, list of hawb_no, list of size warning messages),
    or None if no records found.
    """
    conf = _load_jp_edi_config()
    filename = f"put_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output_path = outbox_dir / filename

    with DBClient() as db:
        rows = _fetch_rows(db, conf["tracking_no_prefix"])

    if not rows:
        logger.info("No records to export.")
        return None

    logger.info("Fetched %d record(s) from DB.", len(rows))

    size_warnings: List[str] = []
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\r\n")
        for row in rows:
            writer.writerow(_build_row(row, conf, size_warnings))

    if size_warnings:
        logger.warning("Size code could not be resolved for %d record(s).", len(size_warnings))

    logger.info("Generated CSV: %s (%d rows)", output_path.name, len(rows))

    hawb_nos = [row["hawb_no"] for row in rows if row.get("hawb_no")]
    return output_path, hawb_nos, size_warnings
