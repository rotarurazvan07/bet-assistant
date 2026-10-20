"""Canonical market key helpers.

Kills the ``odds_key.replace("odds_", "")`` prefix-surgery pattern: the
``cons_``/``odds_`` conventions exist in exactly this module.
"""

from bet_framework.markets.catalog import MARKET_BY_STRIPPED_KEY

ODDS_PREFIX = "odds_"


def stripped_key(odds_key_value: str) -> str:
    """Stripped odds key used by movement payloads ('odds_over_25' -> 'over_25')."""
    return odds_key_value.removeprefix(ODDS_PREFIX)


def lookup_key(stripped: str) -> str:
    """Translate a stripped key back to the Odds-dataclass field used by history rows.

    'btts_yes' -> 'btts_y'; every other market maps to itself. Raises KeyError
    for unknown keys (fail loudly instead of a silent None movement).
    """
    return MARKET_BY_STRIPPED_KEY[stripped].crawler_field
