"""[P1] Pure unit tests for slips router helpers (issue #58, worker B-backend scope).

Covers validate_manual_leg, _dict_to_candidate_leg, _leg_to_dict,
_slip_to_dict, _enum_or_str at branch level (no HTTP layer).
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from conftest import FakeDashboardLogic
from routers.slips import (
    _dict_to_candidate_leg,
    _enum_or_str,
    _leg_to_dict,
    _slip_to_dict,
    validate_manual_leg,
)
from bet_framework.core.type_defs import MarketType, Outcome


def _leg_dict(**overrides) -> dict:
    leg = {
        "match_name": "Real Madrid - Barcelona",
        "market": "1",
        "odds": 1.9,
        "result_url": "https://example.com/match/1",
    }
    leg.update(overrides)
    return leg


class TestValidateManualLegMatchResolution:
    """[P1] Match lookup: separator split vs fuzzy fallback."""

    def test_dash_separator_matches_home_and_away(self):
        logic = FakeDashboardLogic()
        assert validate_manual_leg(_leg_dict(), logic) == {"valid": True}

    def test_vs_separator_matches(self):
        logic = FakeDashboardLogic()
        result = validate_manual_leg(_leg_dict(match_name="Real Madrid vs Barcelona"), logic)
        assert result == {"valid": True}

    def test_fuzzy_fallback_single_team_name(self):
        logic = FakeDashboardLogic()
        assert validate_manual_leg(_leg_dict(match_name="Barcelona"), logic) == {"valid": True}

    def test_unknown_match_returns_invalid_with_error(self):
        logic = FakeDashboardLogic()
        result = validate_manual_leg(_leg_dict(match_name="Atlético Mística"), logic)
        assert result["valid"] is False
        assert result["error"] == "Match not found: Atlético Mística"

    def test_partial_home_away_mismatch_is_invalid(self):
        logic = FakeDashboardLogic()
        result = validate_manual_leg(_leg_dict(match_name="Real Madrid - Valencia"), logic)
        assert result["valid"] is False


class TestValidateManualLegMarket:
    """[P1] Market allow-list."""

    def test_allowed_market_passes(self):
        logic = FakeDashboardLogic()
        assert validate_manual_leg(_leg_dict(market="Over 2.5"), logic) == {"valid": True}

    def test_disallowed_market_rejected(self):
        logic = FakeDashboardLogic()
        result = validate_manual_leg(_leg_dict(market="Corner Over 9.5"), logic)
        assert result["valid"] is False
        assert "Invalid market 'Corner Over 9.5'" in result["error"]
        assert "Over 2.5" in result["error"]  # allowed list surfaced

    def test_enum_market_value_extracted(self):
        from bet_framework.core.type_defs import MarketLabel

        logic = FakeDashboardLogic()
        assert validate_manual_leg(_leg_dict(market=MarketLabel.HOME), logic) == {"valid": True}


class TestValidateManualLegOdds:
    """[P1] Odds sanity checks."""

    def test_numeric_string_odds_coerced(self):
        logic = FakeDashboardLogic()
        assert validate_manual_leg(_leg_dict(odds="2.10"), logic) == {"valid": True}

    def test_zero_odds_rejected(self):
        logic = FakeDashboardLogic()
        result = validate_manual_leg(_leg_dict(odds=0), logic)
        assert result == {"valid": False, "error": "Invalid odds: 0"}

    def test_negative_odds_rejected(self):
        logic = FakeDashboardLogic()
        assert validate_manual_leg(_leg_dict(odds=-1.5), logic)["valid"] is False

    def test_non_numeric_odds_rejected(self):
        logic = FakeDashboardLogic()
        result = validate_manual_leg(_leg_dict(odds="abc"), logic)
        assert result == {"valid": False, "error": "Invalid odds: abc"}

    def test_none_odds_rejected(self):
        logic = FakeDashboardLogic()
        assert validate_manual_leg(_leg_dict(odds=None), logic)["valid"] is False


class TestValidateManualLegUrl:
    """[P2] result_url format check."""

    def test_valid_url_passes(self):
        logic = FakeDashboardLogic()
        assert validate_manual_leg(_leg_dict(), logic) == {"valid": True}

    def test_none_url_is_optional(self):
        logic = FakeDashboardLogic()
        assert validate_manual_leg(_leg_dict(result_url=None), logic) == {"valid": True}

    def test_placeholder_url_rejected(self):
        logic = FakeDashboardLogic()
        result = validate_manual_leg(_leg_dict(result_url="null"), logic)
        assert result == {"valid": False, "error": "Invalid result_url: null"}


class TestDictToCandidateLeg:
    """[P1] Conversion + validation of ManualLeg dicts."""

    def _full(self, **overrides) -> dict:
        d = {
            "match_name": "A - B",
            "market": "1",
            "market_type": "result",
            "odds": 1.9,
            "result_url": "https://x.com/1",
            "consensus": 55.0,
            "sources": 4,
        }
        d.update(overrides)
        return d

    def test_happy_path_builds_candidate_leg(self):
        leg = _dict_to_candidate_leg(self._full())
        assert leg.match_name == "A - B"
        assert leg.market.value == "1"
        assert leg.market_type == MarketType.RESULT
        assert leg.consensus == 55.0
        assert leg.sources == 4
        assert leg.tier == 1
        assert leg.predictions == []

    def test_unknown_market_label_falls_back_to_string(self):
        leg = _dict_to_candidate_leg(self._full(market="Custom Market"))
        assert leg.market == "Custom Market"

    def test_missing_market_raises(self):
        with pytest.raises(ValueError, match="market is required"):
            _dict_to_candidate_leg(self._full(market=None))

    def test_missing_market_type_raises(self):
        with pytest.raises(ValueError, match="market_type is required"):
            _dict_to_candidate_leg(self._full(market_type=None))

    def test_invalid_market_type_raises_with_allowed_values(self):
        with pytest.raises(ValueError, match="Invalid market_type"):
            _dict_to_candidate_leg(self._full(market_type="nonsense"))

    def test_missing_required_fields_raise(self):
        for field in ("match_name", "odds", "result_url", "consensus", "sources"):
            d = self._full()
            d[field] = None
            with pytest.raises(ValueError, match=f"{field} is required"):
                _dict_to_candidate_leg(d)

    def test_non_positive_odds_raises(self):
        with pytest.raises(ValueError, match="Invalid odds"):
            _dict_to_candidate_leg(self._full(odds=0))

    def test_consensus_out_of_range_raises(self):
        with pytest.raises(ValueError, match="Invalid consensus"):
            _dict_to_candidate_leg(self._full(consensus=101.0))

    def test_negative_sources_raises(self):
        with pytest.raises(ValueError, match="Invalid sources"):
            _dict_to_candidate_leg(self._full(sources=-3))

    def test_optional_fields_defaulted(self):
        leg = _dict_to_candidate_leg(self._full(league=None, tier=2, score=0.5))
        assert leg.league is None or "La Liga" in (leg.league or "")
        assert leg.tier == 2
        assert leg.score == 0.5


class TestLegAndSlipSerialization:
    """[P2] _leg_to_dict / _slip_to_dict serialization rules."""

    def test_enum_or_str(self):
        assert _enum_or_str(Outcome.WON) == "Won"
        assert _enum_or_str("plain") == "plain"

    def test_leg_datetime_isoformat(self):
        leg = SimpleNamespace(
            match_name="A",
            datetime=datetime(2030, 1, 1, 12, 0),
            market=Outcome.WON,
            market_type=None,
            odds=2.0,
            status=Outcome.LIVE,
            result_url="https://x.com",
            league="L",
            predictions=[],
        )
        out = _leg_to_dict(leg)
        assert out["datetime"] == "2030-01-01T12:00:00"
        assert out["market"] == "Won"
        assert out["market_type"] is None
        assert out["status"] == "Live"

    def test_leg_datetime_none_stays_none(self):
        leg = SimpleNamespace(
            match_name="A", datetime=None, market="1", market_type="result",
            odds=2.0, status="Pending", result_url=None, league=None, predictions=[],
        )
        assert _leg_to_dict(leg)["datetime"] is None

    def test_leg_datetime_string_passthrough(self):
        leg = SimpleNamespace(
            match_name="A", datetime="2030-01-01 20:00", market="1", market_type="result",
            odds=2.0, status="Pending", result_url=None, league=None, predictions=[],
        )
        assert _leg_to_dict(leg)["datetime"] == "2030-01-01 20:00"

    def test_slip_to_dict_enum_status(self):
        slip = SimpleNamespace(
            slip_id=9,
            date_generated="2030-01-01T10:00:00",
            profile="manual",
            total_odds=3.0,
            units=1.0,
            slip_status=Outcome.LOST,
            legs=[],
        )
        out = _slip_to_dict(slip)
        assert out["slip_id"] == 9
        assert out["slip_status"] == "Lost"
        assert out["legs"] == []

    def test_slip_to_dict_plain_string_status(self):
        slip = SimpleNamespace(
            slip_id=1, date_generated="d", profile="p", total_odds=1.0,
            units=1.0, slip_status="Pending", legs=[],
        )
        assert _slip_to_dict(slip)["slip_status"] == "Pending"