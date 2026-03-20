"""JP EDI - GET batch for tracking CSV."""

import configparser
import logging
import traceback
from datetime import datetime
from pathlib import Path

from lib.lock_manager import acquire_lock, release_lock
from lib.mail_client import send_error_mail
from lib.get_jp_track.fetch_csv import fetch_csv
from lib.get_jp_track.process_csv import process_csv

BASE_DIR     = Path(__file__).resolve().parent.parent
CONFIG_PATH  = BASE_DIR / "config" / "settings.ini"
INBOX_DIR    = BASE_DIR / "work" / "get_inbox"
LOCK_FILE    = BASE_DIR / "work" / "get_jp_track.lock"
LOG_FILE     = BASE_DIR / "logs" / f"get_jp_track_{datetime.now().strftime('%Y%m')}.log"

_config = configparser.ConfigParser()
_config.read(CONFIG_PATH, encoding="utf-8")
S3_BACKUP_ENABLED = _config.getboolean("feature", "s3_backup_enabled", fallback=True)
SFTP_GET_ENABLED  = _config.getboolean("feature", "sftp_get_enabled",  fallback=True)
MAIL_ENABLED      = _config.getboolean("feature", "mail_enabled",      fallback=True)


def init_env() -> None:
    # Create working directories and initialize logger
    for d in (INBOX_DIR, LOG_FILE.parent):
        d.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def _on_format_error(filename: str, error: Exception) -> None:
    if MAIL_ENABLED:
        send_error_mail(
            subject=f"[ERROR] get_jp_track フォーマットエラー: {filename}",
            body=f"フォーマットチェックでエラーが発生しました。\n\nファイル: {filename}\nエラー: {error}",
        )


def _on_complete_with_error(filename: str) -> None:
    if MAIL_ENABLED:
        send_error_mail(
            subject=f"[ERROR] get_jp_track 処理エラー: {filename}",
            body=f"処理中にエラーが発生しました。手動対応が必要です。\n\nファイル: {filename}\n進捗ファイル: work/get_progress/{filename}.progress.json",
        )


if __name__ == "__main__":
    init_env()

    # Step 1: ロックファイルで二重起動を防止
    acquire_lock(LOCK_FILE)
    try:
        # Step 2: JPサーバから追跡CSVをSFTPで取得し get_inbox に保存
        if SFTP_GET_ENABLED:
            fetch_csv(INBOX_DIR)
        else:
            logging.info("SFTP download skipped (disabled).")

        # Step 3: get_inbox のCSVを1件ずつ処理
        #   - 進捗ファイル作成／再開
        #   - S3バックアップ
        #   - フォーマットチェック
        #   - パース・重複チェック・バルクINSERT
        #   - 完走後クリーンアップ
        for f in sorted(INBOX_DIR.glob("*.csv")):
            process_csv(
                f,
                s3_backup_enabled=S3_BACKUP_ENABLED,
                on_format_error=_on_format_error,
                on_complete_with_error=_on_complete_with_error,
            )

    except Exception:
        logging.exception("Batch failed.")
        if MAIL_ENABLED:
            send_error_mail(
                subject="[ERROR] get_jp_track バッチエラー",
                body=f"get_jp_track バッチでエラーが発生しました。\n\n{traceback.format_exc()}",
            )
    finally:
        # Always release lock on exit (normal or abnormal)
        release_lock(LOCK_FILE)
