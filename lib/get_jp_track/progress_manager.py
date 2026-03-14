"""lib/get_progress_manager.py - Progress file management for GET (tracking CSV) batch."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
PROGRESS_DIR = BASE_DIR / "work" / "get_progress"


def _now_str() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


class GetProgressManager:
    def __init__(self, csv_name: str) -> None:
        PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
        self._path = PROGRESS_DIR / f"{csv_name}.progress.json"
        self._csv_name = csv_name
        self._data: dict = {}

    def _save(self) -> None:
        self._data["updated_at"] = _now_str()
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def init(self, s3_backup: str = "unknown", total_rows: Optional[int] = None) -> None:
        """Initialize progress file at the start of processing."""
        self._data = {
            "source_file":    self._csv_name,
            "started_at":     _now_str(),
            "updated_at":     _now_str(),
            "s3_backup":      s3_backup,
            "format_check":       "unknown",
            "format_check_error": None,
            "total_rows":     total_rows,
            "processed_rows": 0,
            "inserted_rows":  0,
            "error_rows": {
                "count": 0,
                "rows":  [],
            },
        }
        self._save()

    def load(self) -> bool:
        """Load existing progress file. Returns True if found."""
        if not self._path.exists():
            return False
        with self._path.open(encoding="utf-8") as f:
            self._data = json.load(f)
        return True

    def set_format_check(self, status: str, error: str = None) -> None:
        """Update format_check status and optionally record error reason."""
        self._data["format_check"] = status
        self._data["format_check_error"] = error
        self._save()

    def update(self, processed_rows: int, inserted_rows: int) -> None:
        """Update processed/inserted row counts and save."""
        self._data["processed_rows"] = processed_rows
        self._data["inserted_rows"]  = inserted_rows
        self._save()

    def add_error_row(self, row_no: int, tracking_no: str, reason: str) -> None:
        """Record a row-level INSERT error."""
        self._data["error_rows"]["rows"].append({
            "row":         row_no,
            "tracking_no": tracking_no,
            "reason":      reason,
        })
        self._data["error_rows"]["count"] = len(self._data["error_rows"]["rows"])
        self._save()


    def set_total_rows(self, total_rows: int) -> None:
        """Update total_rows after parsing."""
        self._data["total_rows"] = total_rows
        self._save()

    def set_s3_backup(self, status: str) -> None:
        """Update s3_backup status."""
        self._data["s3_backup"] = status
        self._save()

    def finalize(self) -> None:
        """Delete progress file if all OK, otherwise leave for manual action."""
        has_issue = (
            self._data.get("error_rows", {}).get("count", 0) > 0
            or self._data.get("s3_backup") == "ng"
            or self._data.get("format_check") == "ng"
        )
        if has_issue:
            logger.warning(
                "%s completed with issues. Progress file left for manual action: %s",
                self._csv_name, self._path,
            )
        else:
            self._path.unlink(missing_ok=True)
            logger.info("%s all OK. Progress file deleted.", self._csv_name)

    @property
    def processed_rows(self) -> int:
        return self._data.get("processed_rows", 0)

    @property
    def inserted_rows(self) -> int:
        return self._data.get("inserted_rows", 0)

    @property
    def s3_backup(self) -> str:
        return self._data.get("s3_backup", "")
