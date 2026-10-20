"""Canonical market key helpers.

Kills the ``odds_key.replace("odds_", "")`` prefix-surgery pattern: the
``cons_``/``odds_`` conventions exist in exactly this module.
"""

from bet_framework.markets.catalog import market_by_key

ODDS_PREFIX = "odds_"


def consensus_key(market: str) -> str:
    """Canonical consensus column key for a market label (e.g. '1' -> 'cons_home')."""
    return market_by_key(market).cons_key


def odds_key(market: str) -> str:
    """Canonical odds column key for a market label (e.g. '1' -> 'odds_home')."""
    return market_by_key(market).odds_key


def stripped_key(odds_key_value: str) -> str:
    """Stripped odds key used by movement payloads ('odds_over_25' -> 'over_25')."""
    return odds_key_value.removeprefix(ODDS_PREFIX)
