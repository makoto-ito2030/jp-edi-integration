"""lib/s3_client.py - S3 client (config self-loading)."""

import configparser
import logging
import sys
from pathlib import Path
from typing import List, Optional

import boto3

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "settings.ini"


def _load_s3_config(section: str) -> dict:
    if not CONFIG_PATH.exists():
        logger.critical("settings.ini not found: %s", CONFIG_PATH)
        sys.exit(1)
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")
    if section not in config:
        logger.critical("Missing [%s] section in %s", section, CONFIG_PATH)
        sys.exit(1)
    s3 = config[section]
    return {
        "bucket": s3["bucket"],
        "prefix": s3["prefix"],
    }


class S3Client:
    def __init__(self, section: str = "s3") -> None:
        """
        section: config section name (default: "s3")
        """
        conf = _load_s3_config(section)
        self._bucket = conf["bucket"]
        self._prefix = conf["prefix"]
        self._client = boto3.client("s3")
        logger.info("S3Client initialized: section=%s bucket=%s prefix=%s",
                    section, self._bucket, self._prefix)

    def upload(self, filepath: Path, key: Optional[str] = None) -> str:
        """
        Upload file to S3.
        key: S3 object key. If not specified, uses {prefix}{filename}.
        Returns the S3 URI.
        """
        filepath = Path(filepath)
        if key is None:
            key = f"{self._prefix}{filepath.name}"
        self._client.upload_file(str(filepath), self._bucket, key)
        uri = f"s3://{self._bucket}/{key}"
        logger.info("Uploaded %s -> %s", filepath.name, uri)
        return uri

    def download(self, key: str, dest: Path) -> None:
        """Download S3 object to local path."""
        dest = Path(dest)
        self._client.download_file(self._bucket, key, str(dest))
        logger.info("Downloaded s3://%s/%s -> %s", self._bucket, key, dest)

    def list_objects(self, prefix: Optional[str] = None) -> List[str]:
        """List object keys under prefix. Returns list of keys."""
        prefix = prefix or self._prefix
        response = self._client.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
        return [obj["Key"] for obj in response.get("Contents", [])]
