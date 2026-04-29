"""
bet_framework.core.outcomes
────────────────────────────
Pure functions for evaluating soccer match results against betting markets.

No state, no database, no configuration — just score + market → outcome.

Public surface
──────────────
  parse_score(raw)                               → (int, int)
  determine_outcome(home, away, market, type)    → Outcome
"""

from __future__ import annotations

from bet_framework.core.types import MarketLabel, MarketType, Outcome


def parse_score(raw: str) -> tuple[int, int]:
    """
    Convert a 'H:A' score string to an (home_goals, away_goals) integer tuple.

    >>> parse_score("2:1")
    (2, 1)
    >>> parse_score("0:0")
    (0, 0)
    """
    h, a = raw.split(":")
    return int(h), int(a)


def determine_outcome(home: int, away: int, market: str, market_type: str) -> Outcome:
    """
    Determine the outcome (Outcome.WON, Outcome.LOST, or Outcome.PENDING) for a single leg given
    the full-time score and the leg's market details.

    Parameters
    ----------
    home        : Home team goals.
    away        : Away team goals.
    market      : Display label for the leg (e.g. '1', 'X', '2', 'Over 2.5', 'Over 1.5', 'Over 0.5', 'Over 3.5', 'Over 4.5').
    market_type : One of MarketType.RESULT, MarketType.BTTS, MarketType.OVER_UNDER_25, MarketType.OVER_UNDER_15, MarketType.OVER_UNDER_05, MarketType.OVER_UNDER_35, MarketType.OVER_UNDER_45.

    Returns
    -------
    Outcome.WON | Outcome.LOST | Outcome.PENDING
    """
    handlers = {
        MarketType.RESULT: _handle_result_market,
        MarketType.BTTS: _handle_btts_market,
        MarketType.OVER_UNDER_25: _handle_over_under_market,
        MarketType.OVER_UNDER_15: _handle_over_under_market,
        MarketType.OVER_UNDER_05: _handle_over_under_market,
        MarketType.OVER_UNDER_35: _handle_over_under_market,
        MarketType.OVER_UNDER_45: _handle_over_under_market,
        MarketType.DOUBLE_CHANCE: _handle_double_chance_market,
    }

    handler = handlers.get(market_type)
    if handler:
        return handler(home, away, market)

    return Outcome.PENDING


def _handle_result_market(home: int, away: int, market: str) -> Outcome:
    """Handle 1X2 (result) market outcomes."""
    if market == MarketLabel.HOME and home > away:
        return Outcome.WON
    if market == MarketLabel.AWAY and away > home:
        return Outcome.WON
    if market == MarketLabel.DRAW and home == away:
        return Outcome.WON
    return Outcome.LOST


def _handle_btts_market(home: int, away: int, market: str) -> Outcome:
    """Handle Both Teams To Score (BTTS) market outcomes."""
    scored = home > 0 and away > 0
    if market == MarketLabel.BTTS_YES and scored:
        return Outcome.WON
    if market == MarketLabel.BTTS_NO and not scored:
        return Outcome.WON
    return Outcome.LOST


def _handle_double_chance_market(home: int, away: int, market: str) -> Outcome:
    """Handle Double Chance market outcomes."""
    if market == MarketLabel.DC_1X and (home >= away):  # Home win or draw (1X)
        return Outcome.WON
    if market == MarketLabel.DC_12 and (home != away):  # Either team wins (12)
        return Outcome.WON
    if market == MarketLabel.DC_X2 and (away >= home):   # Away win or draw (X2)
        return Outcome.WON
    return Outcome.LOST


def _handle_over_under_market(home: int, away: int, market: str) -> Outcome:
    """Handle Over/Under goals market outcomes (0.5, 1.5, 2.5, 3.5, 4.5)."""
    total = home + away
    
    # Determine threshold based on market label
    if market in (MarketLabel.OVER_05, MarketLabel.UNDER_05):
        threshold = 0.5
    elif market in (MarketLabel.OVER_15, MarketLabel.UNDER_15):
        threshold = 1.5
    elif market in (MarketLabel.OVER_35, MarketLabel.UNDER_35):
        threshold = 3.5
    elif market in (MarketLabel.OVER_45, MarketLabel.UNDER_45):
        threshold = 4.5
    else:  # Default to 2.5 for OVER_25, UNDER_25
        threshold = 2.5
    
    if market in (MarketLabel.OVER_05, MarketLabel.OVER_15, MarketLabel.OVER_25, MarketLabel.OVER_35, MarketLabel.OVER_45) and total > threshold:
        return Outcome.WON
    if market in (MarketLabel.UNDER_05, MarketLabel.UNDER_15, MarketLabel.UNDER_25, MarketLabel.UNDER_35, MarketLabel.UNDER_45) and total < threshold:
        return Outcome.WON
    return Outcome.LOST
