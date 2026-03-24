"""lib/db_client.py - RDS (MySQL) client."""

import configparser
from lib.config_loader import load_config
import logging
from lib.exceptions import ConfigError
from pathlib import Path

import pymysql
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "settings.ini"


def _load_db_config() -> dict:
    if not CONFIG_PATH.exists():
        logger.critical("settings.ini not found: %s", CONFIG_PATH)
        raise ConfigError(f"Configuration error: see log for details")
    config = load_config(CONFIG_PATH)
    if "db" not in config:
        logger.critical("Missing [db] section in %s", CONFIG_PATH)
        raise ConfigError(f"Configuration error: see log for details")
    db = config["db"]
    return {
        "host":     db["host"],
        "port":     int(db["port"]),
        "user":     db["user"],
        "password": db["password"],
        "database": db["database"],
        "strict_mode": config.getboolean("db", "strict_mode", fallback=True),
    }


class DBClient:
    def __init__(self) -> None:
        conf = _load_db_config()
        self._host     = conf["host"]
        self._port     = conf["port"]
        self._user     = conf["user"]
        self._password = conf["password"]
        self._database = conf["database"]
        self._strict_mode = conf["strict_mode"]
        self._conn: Optional[pymysql.connections.Connection] = None

    def __enter__(self) -> "DBClient":
        try:
            self._conn = pymysql.connect(
                host=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                database=self._database,
                cursorclass=pymysql.cursors.DictCursor,
                init_command="SET SESSION sql_mode='STRICT_TRANS_TABLES'" if self._strict_mode else None,
            )
        except Exception:
            logger.exception("Failed to connect to %s:%s", self._host, self._port)
            raise
        logger.info("Connected to %s:%s/%s", self._host, self._port, self._database)
        return self

    def __exit__(self, *_) -> None:
        if self._conn:
            self._conn.close()
        logger.info("Disconnected from %s:%s/%s", self._host, self._port, self._database)

    def execute(self, sql: str, params: tuple = ()) -> List[Dict]:
        """Execute SQL and return results."""
        with self._conn.cursor() as cursor:
            cursor.execute(sql, params)
            self._conn.commit()
            return cursor.fetchall()

    def executemany(self, sql: str, params: List[Tuple]) -> None:
        """Execute SQL with multiple parameter sets (e.g. bulk INSERT)."""
        try:
            with self._conn.cursor() as cursor:
                cursor.executemany(sql, params)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            logger.exception("executemany failed, rolled back")
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    with DBClient() as client:
        rows = client.execute("SELECT COUNT(*) AS cnt FROM logistic_track")
        print(f"logistic_track: {rows[0]['cnt']} rows")
        mode = client.execute("SELECT @@SESSION.sql_mode AS sql_mode")
        print(f"sql_mode: {mode[0]['sql_mode']}")
