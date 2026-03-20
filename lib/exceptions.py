"""lib/exceptions.py - Common exceptions for JP EDI integration batch."""


class LockError(Exception):
    """Raised when a lock file already exists (duplicate execution detected)."""


class ConfigError(Exception):
    """Raised when a required configuration file or section is missing."""
