"""JP EDI - PUT batch for shipping CSV."""

import configparser
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

from lib.lock_manager import acquire_lock, release_lock
from lib.mail_client import send_error_mail
from lib.put_jp_edi.generate_csv import generate_csv
from lib.put_jp_edi.send_csv import send_csv
from lib.put_jp_edi.update_jp_download import update_jp_download
from lib.put_jp_edi.backup_csv import backup_csv

BASE_DIR    = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "settings.ini"
OUTBOX_DIR  = BASE_DIR / "work" / "put_outbox"
BACKUP_DIR  = BASE_DIR / "work" / "put_backup"
ERROR_DIR   = BASE_DIR / "work" / "put_error"
LOCK_FILE   = BASE_DIR / "work" / "put_jp_edi.lock"
LOG_FILE    = BASE_DIR / "logs" / f"put_jp_edi_{datetime.now().strftime('%Y%m')}.log"

_config = configparser.ConfigParser()
_config.read(CONFIG_PATH, encoding="utf-8")
SFTP_PUT_ENABLED  = _config.getboolean("feature", "sftp_put_enabled",  fallback=True)
S3_BACKUP_ENABLED = _config.getboolean("feature", "s3_backup_enabled", fallback=True)
MAIL_ENABLED      = _config.getboolean("feature", "mail_enabled",      fallback=True)


def init_env() -> None:
    # Create working directories and initialize logger
    for d in (OUTBOX_DIR, BACKUP_DIR, ERROR_DIR, LOG_FILE.parent):
        d.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


if __name__ == "__main__":
    init_env()
    acquire_lock(LOCK_FILE)
    try:
        # Step 1: DBから出荷CSVを生成し put_outbox に配置
        result = generate_csv(OUTBOX_DIR)
        if result is None:
            logging.info("No records to send. Exiting.")
            sys.exit(0)
        csv_path, hawb_nos, size_warnings = result

        # Step 2: put_outbox のCSVをSFTPでJPサーバへPUT → 成功時は put_backup へ移動
        if SFTP_PUT_ENABLED:
            send_csv(OUTBOX_DIR, BACKUP_DIR, ERROR_DIR)
        else:
            logging.info("SFTP upload skipped (disabled).")

        # Step 3: goods_hawb_ext.jp_download を更新
        update_jp_download(hawb_nos)

        # Step 4: put_backup のCSVをS3へバックアップ → 成功時はファイル削除
        if S3_BACKUP_ENABLED:
            backup_csv(BACKUP_DIR)
        else:
            logging.info("S3 backup skipped (disabled).")

        # Step 5: サイズコード未解決レコードがあればまとめて1件メール通知
        if size_warnings and MAIL_ENABLED:
            send_error_mail(
                subject="[WARN] put_jp_edi サイズコード未解決レコードあり",
                body=(
                    f"サイズコードを解決できなかったレコードが {len(size_warnings)} 件あります。\n"
                    "サイズ項目（No.27）はブランクで送信しました。\n\n"
                    + "\n".join(size_warnings)
                ),
            )

    except Exception:
        logging.exception("Batch failed.")
        if MAIL_ENABLED:
            send_error_mail(
                subject="[ERROR] put_jp_edi バッチエラー",
                body=f"put_jp_edi バッチでエラーが発生しました。\n\n{traceback.format_exc()}",
            )
        sys.exit(1)
    finally:
        release_lock(LOCK_FILE)
