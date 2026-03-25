"""lib/get_jp_track/parse_track_csv.py - Parse V6 tracking CSV.

Body record columns:
  0: 削除区分, 1: 郵便分類コード, 2: 郵便分類名称, 3: 追跡番号,
  4: 顧客側管理番号, 5: 状態発生日時(YYYYMMDDhhmm), 6: 取扱店コード,
  7: 取扱店名, 8: ステータスコード(4桁=コード2桁+補助2桁), 9: 付加日付,
  10: 引受日時, 11: 引受店コード, 12: 引受店名,
  13: 顧客コード①, 14: 顧客コード②, 15: サイズ情報, 16: 予備
"""

import csv

from lib.get_jp_track.constants import STATUS_MAP
from datetime import datetime

DATETIME_FORMAT = "%Y%m%d%H%M"



def parse_csv(filepath):
    """
    Parse V6 CSV and return list of tuples for logistic_track INSERT.
    Skips header record (row 0) and deletion records (削除区分=1).
    Returns: list of tuple (tracking_no, report_date, shipping_club, baggage_status,
                            store_nm_in_charge, create_time, update_time)
    """
    rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filepath, encoding="shift-jis", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header record
        for row in reader:
            # Skip deletion records
            if row[0].strip() == "1":
                continue

            tracking_no        = row[3].strip()
            shipping_club      = row[2].strip()
            report_date        = datetime.strptime(row[5].strip(), DATETIME_FORMAT).strftime("%Y-%m-%d %H:%M:%S")
            store_nm_in_charge = row[7].strip()
            status_code        = row[8].strip()
            baggage_status     = STATUS_MAP.get(status_code, status_code)

            rows.append((
                tracking_no,
                report_date,
                shipping_club,
                baggage_status,
                store_nm_in_charge,
                now,  # create_time
                now,  # update_time
            ))
    return rows
