"""Canonical market catalog - the ONLY place allowed to name a market string.

Order-free and key-indexed; presentation order is owned by the frontend.
Values are FROZEN: byte-identical to the persisted wire format (matches.db
columns, slips.db labels, odds-history JSON keys). Renaming a value is a
data-migration event requiring explicit approval, never a silent edit.

``crawler_field`` is the produced field name on the framework ``Odds``
dataclass (bet_framework/core/Match.py). It differs from the stripped odds
key exactly where the PR #106 bug class was born ('btts_y' vs 'btts_yes'),
so finders and the backend mapper consume this mapping instead of literals.
"""

from typing import NamedTuple


class MarketSpec(NamedTuple):
    """One canonical market row: identity key, label, type, column keys."""

    key: str  # persisted identity, e.g. 'BTTS Yes'
    label: str  # display text (frontend may override presentation labels)
    market_type: str  # category routing key, e.g. 'btts'
    cons_key: str  # consensus column, e.g. 'cons_btts_yes'
    odds_key: str  # odds column, e.g. 'odds_btts_yes'
    crawler_field: str  # Odds dataclass field, e.g. 'btts_y'


MARKET_CATALOG: tuple[MarketSpec, ...] = (
    MarketSpec("1", "1", "result", "cons_home", "odds_home", "home"),
    MarketSpec("X", "X", "result", "cons_draw", "odds_draw", "draw"),
    MarketSpec("2", "2", "result", "cons_away", "odds_away", "away"),
    MarketSpec(
        "Over 2.5",
        "Over 2.5",
        "over_under_25",
        "cons_over_25",
        "odds_over_25",
        "over_25",
    ),
    MarketSpec(
        "Under 2.5",
        "Under 2.5",
        "over_under_25",
        "cons_under_25",
        "odds_under_25",
        "under_25",
    ),
    MarketSpec(
        "BTTS Yes", "BTTS Yes", "btts", "cons_btts_yes", "odds_btts_yes", "btts_y"
    ),
    MarketSpec("BTTS No", "BTTS No", "btts", "cons_btts_no", "odds_btts_no", "btts_n"),
    MarketSpec(
        "Over 0.5",
        "Over 0.5",
        "over_under_05",
        "cons_over_05",
        "odds_over_05",
        "over_05",
    ),
    MarketSpec(
        "Under 0.5",
        "Under 0.5",
        "over_under_05",
        "cons_under_05",
        "odds_under_05",
        "under_05",
    ),
    MarketSpec(
        "Over 1.5",
        "Over 1.5",
        "over_under_15",
        "cons_over_15",
        "odds_over_15",
        "over_15",
    ),
    MarketSpec(
        "Under 1.5",
        "Under 1.5",
        "over_under_15",
        "cons_under_15",
        "odds_under_15",
        "under_15",
    ),
    MarketSpec(
        "Over 3.5",
        "Over 3.5",
        "over_under_35",
        "cons_over_35",
        "odds_over_35",
        "over_35",
    ),
    MarketSpec(
        "Under 3.5",
        "Under 3.5",
        "over_under_35",
        "cons_under_35",
        "odds_under_35",
        "under_35",
    ),
    MarketSpec(
        "Over 4.5",
        "Over 4.5",
        "over_under_45",
        "cons_over_45",
        "odds_over_45",
        "over_45",
    ),
    MarketSpec(
        "Under 4.5",
        "Under 4.5",
        "over_under_45",
        "cons_under_45",
        "odds_under_45",
        "under_45",
    ),
    MarketSpec("1X", "1X", "double_chance", "cons_dc_1x", "odds_dc_1x", "dc_1x"),
    MarketSpec("12", "12", "double_chance", "cons_dc_12", "odds_dc_12", "dc_12"),
    MarketSpec("X2", "X2", "double_chance", "cons_dc_x2", "odds_dc_x2", "dc_x2"),
)

MARKET_BY_KEY: dict[str, MarketSpec] = {spec.key: spec for spec in MARKET_CATALOG}
MARKET_BY_CRAWLER_FIELD: dict[str, MarketSpec] = {
    spec.crawler_field: spec for spec in MARKET_CATALOG
}


def market_by_key(market: str) -> MarketSpec:
    """Key-indexed lookup (never positional). Raises KeyError for unknown markets."""
    return MARKET_BY_KEY[market]
