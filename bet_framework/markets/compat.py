"""Tolerant boundary coercion helpers (AC-06).

Collapses the ad-hoc string-vs-enum policies (hasattr duck-typing,
try/except MarketType(str), _enum_or_str) into one reader-side policy.
"""

from bet_framework.markets.catalog import MARKET_BY_KEY
from bet_framework.markets.enums import MarketKey, MarketType

_TYPES = {mt.value for mt in MarketType}


def coerce_key(value: object) -> str:
    """Accept a MarketKey, its .value, or a raw label string; return the key string."""
    if isinstance(value, MarketKey):
        return value.value
    text = value if isinstance(value, str) else str(value)
    if text not in MARKET_BY_KEY:
        raise ValueError(f"unknown market key: {text!r}")
    return text


def coerce_type(value: object) -> str:
    """Accept a MarketType, its .value, or a raw type string; return the type string."""
    if isinstance(value, MarketType):
        return value.value
    text = value if isinstance(value, str) else str(value)
    if text not in _TYPES:
        raise ValueError(f"unknown market type: {text!r}")
    return text
