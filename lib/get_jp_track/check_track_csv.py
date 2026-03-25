"""lib/get_jp_track/check_track_csv.py - Format check for V6 tracking CSV.

V6 CSV format (variable length, shift-jis):
  Row 0: header record (file version, record count, etc.)
  Row 1+: body records (17 columns)

Body record columns:
  0: 削除区分, 1: 郵便分類コード, 2: 郵便分類名称, 3: 追跡番号,
  4: 顧客側管理番号, 5: 状態発生日時(YYYYMMDDhhmm), 6: 取扱店コード,
  7: 取扱店名, 8: ステータスコード(4桁), 9: 付加日付,
  10: 引受日時, 11: 引受店コード, 12: 引受店名,
  13: 顧客コード①, 14: 顧客コード②, 15: サイズ情報, 16: 予備
"""

import csv
import sys
from datetime import datetime
from pathlib import Path

EXPECTED_COLUMNS = 17
DATETIME_FORMAT = "%Y%m%d%H%M"


def validate_file(filepath):
    """
    File check: correct number of columns.
    Row check: no null/empty values in key fields, valid datetime format.
    Raises ValueError on failure.
    """
    with open(filepath, encoding="shift-jis", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        raise ValueError("No body records found (only header or empty file)")

    # Skip row 0 (header record), validate from row 1
    for i, row in enumerate(rows[1:], start=2):
        if len(row) != EXPECTED_COLUMNS:
            raise ValueError(f"Row {i}: invalid column count: {len(row)} (expected: {EXPECTED_COLUMNS})")
        # Key fields must not be empty
        for col_idx, col_name in [(2, "postal_class_name"), (3, "tracking_no"), (7, "store_name"), (8, "status_code")]:
            if row[col_idx].strip() == "":
                raise ValueError(f"Row {i}: empty value in {col_name}")
        # Datetime format check
        try:
            datetime.strptime(row[5].strip(), DATETIME_FORMAT)
        except ValueError:
            raise ValueError(f"Row {i}: invalid datetime format '{row[5]}'")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_track_csv.py <csv_file_path>")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"File not found: {filepath}")
        sys.exit(1)

    try:
        validate_file(filepath)
        print(f"OK: {filepath.name}")
    except ValueError as e:
        print(f"NG: {e}")
        sys.exit(1)
