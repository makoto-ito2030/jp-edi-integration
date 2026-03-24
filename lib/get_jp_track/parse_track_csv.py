"""lib/get_parse_track_csv.py - Parse and convert tracking CSV."""

import csv
from datetime import datetime

# Columns: tracking_no, store_name, handling_datetime, status_code, status
SHIPPING_CLUB = "Japan Post"

def parse_csv(filepath):
    """
    Parse CSV and return list of tuples for logistic_track INSERT.
    Returns: list of tuple (tracking_no, report_date, shipping_club, baggage_status,
                            store_nm_in_charge, create_time, update_time)
    """
    rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filepath, encoding="shift-jis", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            tracking_no        = row[0].strip()
            store_nm_in_charge = row[1].strip()
            report_date        = datetime.strptime(row[2].strip(), "%Y/%m/%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
            # row[3] status_code is not used
            baggage_status     = row[4].strip()

            rows.append((
                tracking_no,
                report_date,
                SHIPPING_CLUB,
                baggage_status,
                store_nm_in_charge,
                now,  # create_time
                now,  # update_time
            ))
    return rows
