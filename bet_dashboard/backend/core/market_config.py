"""
Single source of truth for market configuration in the backend.
Reorder entries here to change market order.
"""

from typing import NamedTuple


class MarketDef(NamedTuple):
    """Market definition with all required fields."""

    market: str  # Market identifier (e.g., '1', 'X', 'Over 2.5')
    cons_key: str  # Key for consensus column in DataFrame
    odds_key: str  # Key for odds column in DataFrame
    market_type: str  # Market type for categorization


# Market definitions in order
MARKET_DEFINITIONS = [
    MarketDef("1", "cons_home", "odds_home", "result"),
    MarketDef("X", "cons_draw", "odds_draw", "result"),
    MarketDef("2", "cons_away", "odds_away", "result"),
    MarketDef("Over 2.5", "cons_over_25", "odds_over_25", "over_under_25"),
    MarketDef("Under 2.5", "cons_under_25", "odds_under_25", "over_under_25"),
    MarketDef("BTTS Yes", "cons_btts_yes", "odds_btts_yes", "btts"),
    MarketDef("BTTS No", "cons_btts_no", "odds_btts_no", "btts"),
    MarketDef("Over 0.5", "cons_over_05", "odds_over_05", "over_under_05"),
    MarketDef("Under 0.5", "cons_under_05", "odds_under_05", "over_under_05"),
    MarketDef("Over 1.5", "cons_over_15", "odds_over_15", "over_under_15"),
    MarketDef("Under 1.5", "cons_under_15", "odds_under_15", "over_under_15"),
    MarketDef("Over 3.5", "cons_over_35", "odds_over_35", "over_under_35"),
    MarketDef("Under 3.5", "cons_under_35", "odds_under_35", "over_under_35"),
    MarketDef("Over 4.5", "cons_over_45", "odds_over_45", "over_under_45"),
    MarketDef("Under 4.5", "cons_under_45", "odds_under_45", "over_under_45"),
    MarketDef("1X", "cons_dc_1x", "odds_dc_1x", "double_chance"),
    MarketDef("12", "cons_dc_12", "odds_dc_12", "double_chance"),
    MarketDef("X2", "cons_dc_x2", "odds_dc_x2", "double_chance"),
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
