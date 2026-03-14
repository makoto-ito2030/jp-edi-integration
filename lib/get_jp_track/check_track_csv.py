"""lib/get_check_track_csv.py - Format check for tracking CSV.

Usage:
    python lib/get_check_track_csv.py <csv_file_path>
"""

import csv
import sys
from datetime import datetime
from pathlib import Path

# TODO: Confirm actual CSV column count after receiving real CSV from Japan Post
EXPECTED_COLUMNS = 5

def validate_file(filepath):
    """
    File check: correct number of columns.
    Row check: no null/empty values, valid datetime format.
    Raises ValueError on failure.
    """
    with open(filepath, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        if header is None or len(header) != EXPECTED_COLUMNS:
            raise ValueError(f"Invalid column count: {len(header) if header else 0} (expected: {EXPECTED_COLUMNS})")

        for i, row in enumerate(reader, start=2):
            if len(row) != EXPECTED_COLUMNS:
                raise ValueError(f"Row {i}: invalid column count")
            if any(v.strip() == "" for v in row):
                raise ValueError(f"Row {i}: empty value found {row}")
            # TODO: Confirm actual datetime format after receiving real CSV from Japan Post
            try:
                datetime.strptime(row[2].strip(), "%Y/%m/%d %H:%M:%S")
            except ValueError:
                raise ValueError(f"Row {i}: invalid datetime format '{row[2]}'")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python get_check_track_csv.py <csv_file_path>")
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
