"""Canonical market identifiers and data keys shared across the application."""

from typing import NamedTuple


class MarketDef(NamedTuple):
    """Market definition with all fields needed by the crawler and dashboard."""

    market: str
    cons_key: str
    odds_key: str
    market_type: str


# Reorder entries here to change market order throughout the backend/framework.
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

ALLOWED_MARKETS = {market.market for market in MARKET_DEFINITIONS}
ALL_MARKETS = [market.market for market in MARKET_DEFINITIONS]
CONSENSUS_COLUMNS = [market.cons_key for market in MARKET_DEFINITIONS]
ODDS_COLUMNS = [market.odds_key for market in MARKET_DEFINITIONS]
MARKET_BY_ID = {market.market: market for market in MARKET_DEFINITIONS}
