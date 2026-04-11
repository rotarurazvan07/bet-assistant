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
    market      : Display label for the leg (e.g. '1', 'X', '2', 'Over 2.5').
    market_type : One of MarketType.RESULT, MarketType.BTTS, MarketType.OVER_UNDER_25.

    Returns
    -------
    Outcome.WON | Outcome.LOST | Outcome.PENDING
    """
    handlers = {
        MarketType.RESULT: _handle_result_market,
        MarketType.BTTS: _handle_btts_market,
        MarketType.OVER_UNDER_25: _handle_over_under_market,
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


def _handle_over_under_market(home: int, away: int, market: str) -> Outcome:
    """Handle Over/Under 2.5 goals market outcomes."""
    total = home + away
    if market == MarketLabel.OVER_25 and total >= 3:
        return Outcome.WON
    if market == MarketLabel.UNDER_25 and total < 3:
        return Outcome.WON
    return Outcome.LOST
