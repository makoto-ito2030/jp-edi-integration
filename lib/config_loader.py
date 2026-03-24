"""lib/config_loader.py - Configuration file loader with BOM handling."""

import configparser
from pathlib import Path


def load_config(path: Path) -> configparser.ConfigParser:
    """Read settings.ini, stripping UTF-8 BOM if present."""
    config = configparser.ConfigParser()
    text = path.read_bytes()
    if text.startswith(b"\xef\xbb\xbf"):
        text = text[3:]
    config.read_string(text.decode("utf-8"))
    return config
