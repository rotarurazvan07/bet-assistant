"""Canonical market key helpers.

Kills the ``odds_key.replace("odds_", "")`` prefix-surgery pattern: the
``cons_``/``odds_`` conventions exist in exactly this module.
"""

import warnings

from bet_framework.markets.catalog import MARKET_BY_KEY
from bet_framework.markets.views import LEGACY_LABEL_TO_KEY

ODDS_PREFIX = "odds_"


def stripped_key(odds_key_value: str) -> str:
    """Stripped odds key used by movement payloads ('odds_over_25' -> 'over_25')."""
    return odds_key_value.removeprefix(ODDS_PREFIX)


def legacy_market_key(value: object) -> str:
    """One-cycle legacy-read shim (D2): accept pre-U1 canonical label spellings.

    Before key unification (story 114-2, U1) slip legs and browser storage
    persisted display labels ('1', 'BTTS Yes', 'Over 2.5'). Those rows remain
    in old slips.db files and user localStorage. This helper maps the legacy
    spelling to the canonical key at the READ boundary; the write path emits
    the canonical key only. Retire after one release cycle: rows written by
    versions >= U1 no longer need translation.

    Known keys pass through unchanged; unknown values raise (fail loudly).
    """
    text = value if isinstance(value, str) else str(value)
    if text in MARKET_BY_KEY:
        return text
    if text in LEGACY_LABEL_TO_KEY:
        warnings.warn(
            f"legacy market label {text!r} read from old slip data; it will be rewritten in canonical spelling on next save",
            DeprecationWarning,
            stacklevel=2,
        )
        return LEGACY_LABEL_TO_KEY[text]
    raise KeyError(f"unknown market key: {text!r}")
