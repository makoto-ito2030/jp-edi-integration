"""lib/put_jp_edi/sanitize.py - Sanitize field values for DENFD CSV."""

_FORBIDDEN = str.maketrans({
    '"':  None,   # ダブルクォーテーション（囲み文字として認識される）
    ',':  None,   # カンマ（区切り文字として認識される）
    '\0': None,   # NULL
    '\t': None,   # 水平タブ
    '\v': None,   # 垂直タブ
    '\n': None,   # LF
    '\r': None,   # CR
})


def sanitize(value: str) -> str:
    """Remove forbidden characters from a field value."""
    if not value:
        return value
    return value.translate(_FORBIDDEN)
