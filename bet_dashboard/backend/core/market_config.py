"""
Deprecated facade: canonical market configuration now lives in
``bet_framework.markets`` (single source of truth). This module keeps the
historical names/shapes for existing consumers during the burn-down and is
deleted when the last reference migrates (zero-reference gate).

Deprecation policy: ``bet_framework.markets.catalog`` owns identity and every
derived name below is materialized from it. Values are FROZEN (no renames:
matches.db columns, slips.db labels, odds-history JSON keys stay as-is).
"""

from typing import NamedTuple

from bet_framework.markets.catalog import (  # noqa: F401  (re-exported for consumers)
    MARKET_CATALOG,
    MarketSpec,
)


class MarketDef(NamedTuple):
    """Market definition with all required fields (legacy shape)."""

    market: str
    cons_key: str
    odds_key: str
    market_type: str


# Legacy ordered list view, materialized from the canonical order-free catalog.
MARKET_DEFINITIONS: list[MarketDef] = [
    MarketDef(spec.key, spec.cons_key, spec.odds_key, spec.market_type)
    for spec in MARKET_CATALOG
]

# Set of allowed market identifiers for validation
ALLOWED_MARKETS = {m.market for m in MARKET_DEFINITIONS}

# List of all market identifiers in order
ALL_MARKETS = [m.market for m in MARKET_DEFINITIONS]

# Consensus column names
CONSENSUS_COLUMNS = [m.cons_key for m in MARKET_DEFINITIONS]

# Odds column names
ODDS_COLUMNS = [m.odds_key for m in MARKET_DEFINITIONS]

# Map market identifier to its definition
MARKET_BY_ID = {m.market: m for m in MARKET_DEFINITIONS}
