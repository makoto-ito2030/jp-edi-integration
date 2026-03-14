"""lib/sftp_client.py - SFTP PUT / GET utility."""

import configparser
import logging
import sys
from pathlib import Path
from typing import List, Optional

import paramiko

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.ini"


def _load_sftp_config() -> dict:
    if not CONFIG_PATH.exists():
        logger.critical("settings.ini not found: %s", CONFIG_PATH)
        sys.exit(1)
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")
    if "sftp" not in config:
        logger.critical("Missing [sftp] section in %s", CONFIG_PATH)
        sys.exit(1)
    sftp = config["sftp"]
    return {
        "host":     sftp["host"],
        "port":     int(sftp["port"]),
        "user":     sftp["user"],
        "password": sftp["password"],
        "put_dir":  sftp["put_dir"],
        "get_dir":  sftp["get_dir"],
    }


class SFTPClient:
    def __init__(self) -> None:
        conf = _load_sftp_config()
        self._host     = conf["host"]
        self._port     = conf["port"]
        self._user     = conf["user"]
        self._password = conf["password"]
        self._get_dir  = conf["get_dir"]
        self._put_dir  = conf["put_dir"]
        self._sftp: Optional[paramiko.SFTPClient] = None
        self._transport: Optional[paramiko.Transport] = None

    def __enter__(self) -> "SFTPClient":
        try:
            self._transport = paramiko.Transport((self._host, self._port))
            self._transport.connect(username=self._user, password=self._password)
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
        except Exception:
            logger.exception("Failed to connect to %s:%s", self._host, self._port)
            raise
        logger.info("Connected to %s:%s", self._host, self._port)
        return self

    def __exit__(self, *_) -> None:
        if self._sftp:
            self._sftp.close()
        if self._transport:
            self._transport.close()
        logger.info("Disconnected from %s:%s", self._host, self._port)

    def put(self, local_path: Path, remote_filename: Optional[str] = None) -> None:
        """Upload a local file to remote. Defaults to put_dir."""
        local_path = Path(local_path)
        remote_path = f"{self._put_dir}/{remote_filename or local_path.name}"
        self._sftp.put(str(local_path), remote_path)
        logger.info("PUT %s -> %s", local_path.name, remote_path)

    def get(self, remote_filename: str, local_path: Optional[Path] = None) -> None:
        """Download a remote file to local. Defaults to get_dir as remote base."""
        remote_path = f"{self._get_dir}/{remote_filename}"
        local_path = Path(local_path) if local_path else Path(remote_filename).name
        self._sftp.get(remote_path, str(local_path))
        logger.info("GET %s -> %s", remote_path, local_path)

    def listdir(self, remote_path: Optional[str] = None) -> List[str]:
        """List files in a remote directory. Defaults to get_dir."""
        return self._sftp.listdir(remote_path or self._get_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    conf = _load_sftp_config()
    with SFTPClient() as client:
        files = client.listdir()
        print(f"Connected: {len(files)} files in {conf['get_dir']}")
