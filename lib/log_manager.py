"""lib/log_manager.py - Log file rotation utility."""

from datetime import datetime
from pathlib import Path


def cleanup_old_logs(log_dir: Path, prefix: str, keep_months: int) -> None:
    """Delete log files older than keep_months months."""
    threshold = datetime.now().replace(day=1)
    for _ in range(keep_months):
        if threshold.month == 1:
            threshold = threshold.replace(year=threshold.year - 1, month=12)
        else:
            threshold = threshold.replace(month=threshold.month - 1)
    for f in log_dir.glob(f"{prefix}_*.log"):
        try:
            if datetime.strptime(f.stem.replace(f"{prefix}_", ""), "%Y%m") < threshold:
                f.unlink()
        except ValueError:
            pass
