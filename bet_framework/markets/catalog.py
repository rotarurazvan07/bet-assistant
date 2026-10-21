"""Canonical market catalog - the ONLY place allowed to name a market string.

Order-free and key-indexed; presentation order is owned by the frontend.
``key`` IS the persisted DB/Odds field spelling ('home', 'over_25',
'btts_yes', 'dc_1x'): no translation layer exists between the canonical
identity and the persisted format. ``label`` carries the human display
text for presentation. ``cons_key``/``odds_key`` remain the DB column
names. Renaming any of these is a data-migration event requiring
explicit approval, never a silent edit.
"""

from typing import NamedTuple


class MarketSpec(NamedTuple):
    """One canonical market row: identity key, display label, type, column keys."""

    key: str  # persisted identity == Odds field spelling, e.g. 'btts_yes'
    label: str  # display text, e.g. 'BTTS Yes'
    market_type: str  # category routing key, e.g. 'btts'
    cons_key: str  # consensus column, e.g. 'cons_btts_yes'
    odds_key: str  # odds column, e.g. 'odds_btts_yes'


MARKET_CATALOG: tuple[MarketSpec, ...] = (
    MarketSpec("home", "1", "result", "cons_home", "odds_home"),
    MarketSpec("draw", "X", "result", "cons_draw", "odds_draw"),
    MarketSpec("away", "2", "result", "cons_away", "odds_away"),
    MarketSpec("over_25", "Over 2.5", "over_under_25", "cons_over_25", "odds_over_25"),
    MarketSpec("under_25", "Under 2.5", "over_under_25", "cons_under_25", "odds_under_25"),
    MarketSpec("btts_yes", "BTTS Yes", "btts", "cons_btts_yes", "odds_btts_yes"),
    MarketSpec("btts_no", "BTTS No", "btts", "cons_btts_no", "odds_btts_no"),
    MarketSpec("over_05", "Over 0.5", "over_under_05", "cons_over_05", "odds_over_05"),
    MarketSpec("under_05", "Under 0.5", "over_under_05", "cons_under_05", "odds_under_05"),
    MarketSpec("over_15", "Over 1.5", "over_under_15", "cons_over_15", "odds_over_15"),
    MarketSpec("under_15", "Under 1.5", "over_under_15", "cons_under_15", "odds_under_15"),
    MarketSpec("over_35", "Over 3.5", "over_under_35", "cons_over_35", "odds_over_35"),
    MarketSpec("under_35", "Under 3.5", "over_under_35", "cons_under_35", "odds_under_35"),
    MarketSpec("over_45", "Over 4.5", "over_under_45", "cons_over_45", "odds_over_45"),
    MarketSpec("under_45", "Under 4.5", "over_under_45", "cons_under_45", "odds_under_45"),
    MarketSpec("dc_1x", "1X", "double_chance", "cons_dc_1x", "odds_dc_1x"),
    MarketSpec("dc_12", "12", "double_chance", "cons_dc_12", "odds_dc_12"),
    MarketSpec("dc_x2", "X2", "double_chance", "cons_dc_x2", "odds_dc_x2"),
)

MARKET_BY_KEY: dict[str, MarketSpec] = {spec.key: spec for spec in MARKET_CATALOG}
MARKET_BY_STRIPPED_KEY: dict[str, MarketSpec] = {spec.odds_key.removeprefix("odds_"): spec for spec in MARKET_CATALOG}


def market_by_key(market: str) -> MarketSpec:
    """Key-indexed lookup (never positional). Raises KeyError for unknown markets."""
    return MARKET_BY_KEY[market]
