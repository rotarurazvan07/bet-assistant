"""
bet_framework.core.utils
─────────────────────────
General-purpose helpers with no domain dependency.

These functions deal with data coercion and validation primitives that
are reused across the bet_framework package.

Public surface
──────────────
  is_valid_url(url)        → bool
  coerce_datetime_str(dt)  → str | None
"""

from __future__ import annotations

from typing import Any


def is_valid_url(url: Any) -> bool:
    """
    Return True if *url* is a usable result URL.

    Rejects None, NaN, empty strings, and the literal strings 'none'/'null'.

    >>> is_valid_url("http://soccervista.com/match")
    True
    >>> is_valid_url(None)
    False
    >>> is_valid_url("null")
    False
    >>> is_valid_url("")
    False
    """
    import math

    if url is None:
        return False
    try:
        if math.isnan(float(url)):
            return False
    except (TypeError, ValueError):
        pass
    stripped = str(url).strip().lower()
    return bool(stripped) and stripped not in ("none", "null")


def coerce_datetime_str(dt: Any) -> str | None:
    """
    Coerce *dt* to an ISO-format string, or return None if not present.

    Accepts datetime objects, pandas Timestamps, and strings that are already
    in ISO format.

    >>> from datetime import datetime
    >>> coerce_datetime_str(datetime(2025, 3, 15, 20, 0))
    '2025-03-15T20:00:00'
    >>> coerce_datetime_str(None) is None
    True
    """
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)
