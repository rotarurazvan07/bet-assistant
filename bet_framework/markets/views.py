"""Key-indexed lookup views over the canonical catalog (AC-05).

Every derived structure is addressed by key - never by list position. If a
consumer needs display order it declares it itself (the frontend owns order).
"""

from bet_framework.markets.catalog import MARKET_CATALOG, MarketSpec

MARKET_BY_KEY: dict[str, MarketSpec] = {spec.key: spec for spec in MARKET_CATALOG}

KEYS_BY_TYPE: dict[str, list[str]] = {}
for _spec in MARKET_CATALOG:
    KEYS_BY_TYPE.setdefault(_spec.market_type, []).append(_spec.key)

# Type -> [(cons_key, odds_key, key)] replacing the positional MARKET_MAP build.
MARKET_MAP_V2: dict[str, list[tuple[str, str, str]]] = {
    market_type: [
        (spec.cons_key, spec.odds_key, spec.key)
        for spec in MARKET_CATALOG
        if spec.market_type == market_type
    ]
    for market_type in KEYS_BY_TYPE
}

# Stripped odds keys used by movement payloads ('odds_over_25' -> 'over_25').
STRIPPED_ODDS_KEYS: tuple[str, ...] = tuple(
    spec.odds_key.removeprefix("odds_") for spec in MARKET_CATALOG
)
