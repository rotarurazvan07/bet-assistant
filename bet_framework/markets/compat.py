"""Tolerant boundary coercion helpers (AC-06).

Collapses the ad-hoc string-vs-enum policies (hasattr duck-typing,
try/except MarketType(str), _enum_or_str) into one reader-side policy.
"""

from bet_framework.markets.catalog import MARKET_BY_KEY
from bet_framework.markets.enums import MarketType

_TYPES = {mt.value for mt in MarketType}


def _enum_value(value: object) -> object:
    """Unwrap any enum-like object to its .value (handles legacy (str, Enum) too)."""
    return getattr(value, "value", value)


def coerce_key(value: object) -> str:
    """Accept a MarketKey/legacy enum, its .value, or a raw label string; return the key string."""
    text = _enum_value(value)
    text = text if isinstance(text, str) else str(text)
    if text not in MARKET_BY_KEY:
        raise ValueError(f"unknown market key: {text!r}")
    return text


def coerce_type(value: object) -> str:
    """Accept a MarketType/legacy enum, its .value, or a raw type string; return the type string."""
    text = _enum_value(value)
    text = text if isinstance(text, str) else str(text)
    if text not in _TYPES:
        raise ValueError(f"unknown market type: {text!r}")
    return text
