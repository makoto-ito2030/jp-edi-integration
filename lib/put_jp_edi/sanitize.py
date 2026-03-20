"""lib/put_jp_edi/sanitize.py - Sanitize field values for DENFD CSV."""

_FORBIDDEN = str.maketrans({
    '"':  None,   # double quote (interpreted as enclosure character)
    ',':  None,   # comma (interpreted as delimiter)
    '\0': None,   # null
    '\t': None,   # horizontal tab
    '\v': None,   # vertical tab
    '\n': None,   # line feed
    '\r': None,   # carriage return
})


def sanitize(value: str) -> str:
    """Remove forbidden characters from a field value."""
    if not value:
        return value
    return value.translate(_FORBIDDEN)
