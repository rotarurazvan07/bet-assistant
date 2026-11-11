"""BetLeg / BetSlip post-init clamping behavior.

Merged from the former standalone helper-gap suite; kept with the
framework slip dataclasses so clamp regressions are caught next to their
owners.
"""

import math

from core.Slip import BetLeg, BetSlip
from markets.enums import MarketKey, MarketType, Outcome


def _leg(**overrides) -> BetLeg:
    payload = {
        "match_name": "Team A - Team B",
        "datetime": "2026-01-01T12:00:00",
        "market": MarketKey.HOME,
        "market_type": MarketType.RESULT,
        "odds": 1.90,
        "status": Outcome.PENDING,
        "result_url": "https://example.test/match/1",
    }
    payload.update(overrides)
    return BetLeg(**payload)


def _slip(**overrides) -> BetSlip:
    payload = {
        "slip_id": 1,
        "date_generated": "2026-01-01T12:00:00",
        "profile": "balanced",
        "total_odds": 2.50,
        "units": 2.0,
    }
    payload.update(overrides)
    return BetSlip(**payload)

class TestBetLegPostInitClamps:
    """BetLeg/__post_init__ normalizes league labels and odds."""

    def test_nan_league_becomes_none(self) -> None:
        leg = _leg(league=float("nan"))
        assert leg.league is None

    def test_none_like_league_strings_become_none(self) -> None:
        for label in ("nan", "None", "NULL"):
            leg = _leg(league=label)
            assert leg.league is None

    def test_non_string_league_is_stringified(self) -> None:
        leg = _leg(league=42)
        assert leg.league == "42"

    def test_nan_odds_reset_to_default(self) -> None:
        leg = _leg(odds=float("nan"))
        assert leg.odds == 1.00

    def test_infinite_odds_reset_to_default(self) -> None:
        leg = _leg(odds=float("inf"))
        assert leg.odds == 1.00

    def test_negative_infinite_odds_reset_to_default(self) -> None:
        leg = _leg(odds=float("-inf"))
        assert leg.odds == 1.00

    def test_valid_odds_pass_through(self) -> None:
        leg = _leg(odds=2.35)
        assert leg.odds == 2.35


class TestBetSlipPostInitClamps:
    """BetSlip/__post_init__ clamps degenerate total_odds and units."""

    def test_nan_total_odds_resets_to_default(self) -> None:
        slip = _slip(total_odds=float("nan"))
        assert slip.total_odds == 1.00

    def test_units_none_becomes_zero(self) -> None:
        slip = _slip(units=None)
        assert slip.units == 0.0

    def test_nan_units_reset_to_default(self) -> None:
        slip = _slip(units=float("nan"))
        assert slip.units == 1.0

    def test_infinite_units_reset_to_default(self) -> None:
        slip = _slip(units=float("inf"))
        assert slip.units == 1.0

    def test_valid_values_pass_through(self) -> None:
        slip = _slip(total_odds=3.5, units=2.0)
        assert slip.total_odds == 3.5
        assert slip.units == 2.0
