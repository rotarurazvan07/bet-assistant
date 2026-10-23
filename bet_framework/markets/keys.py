"""Canonical market key helpers.

Kills the ``odds_key.replace("odds_", "")`` prefix-surgery pattern: the
``cons_``/``odds_`` conventions exist in exactly this module.
"""

ODDS_PREFIX = "odds_"


def stripped_key(odds_key_value: str) -> str:
    """Stripped odds key used by movement payloads ('odds_over_25' -> 'over_25')."""
    return odds_key_value.removeprefix(ODDS_PREFIX)
