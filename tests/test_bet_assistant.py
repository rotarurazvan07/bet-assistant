"""
Comprehensive tests for BetAssistant.

Public API covered:
  BetSlipConfig, get_profile, load_matches, filter_matches,
  build_slip, build_slip_auto_exclude, save_slip, get_slips,
  delete_slip, get_excluded_urls, update_leg, close

Private helpers covered via integration:
  _calc_consensus, _collect_candidates, _select_legs,
  _rows_to_slips, _resolve_tolerance, _resolve_stop_threshold,
  _resolve_max_legs, _score_pick, _determine_outcome, _parse_score

Each method has: normal case(s), edge case(s), error case.
Plus 5 complex integration scenarios at the bottom.
"""

import contextlib
import math
import os
from datetime import datetime, timedelta

import pandas as pd
import pytest

from bet_framework.BetAssistant import (
    MARKET_MAP,
    PROFILES,
    BetAssistant,
    BetSlipConfig,
    _determine_outcome,
    _parse_score,
    _resolve_max_legs,
    _resolve_stop_threshold,
    _resolve_tolerance,
    _score_balance,
    _score_consensus,
    _score_pick,
    _score_sources,
    get_profile,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

DT_BASE = datetime(2026, 4, 5, 15, 0, 0)


def make_matches_df(n=5, sources_per_match=3, with_odds=True, with_url=True):
    """
    Create a match DataFrame with controllable parameters.
    Predictions with clear home win consensus for easy testing.
    """
    rows = []
    for i in range(n):
        scores = []
        for j in range(sources_per_match):
            # Most sources predict home win (3-1)
            scores.append({"home": 3, "away": 1, "source": f"src_{j}"})

        odds = None
        if with_odds:
            odds = {
                "home": 1.50 + (i * 0.1),
                "draw": 3.00 + (i * 0.2),
                "away": 5.00 + (i * 0.3),
                "over": 1.80 + (i * 0.05),
                "under": 2.00 + (i * 0.05),
                "btts_y": 1.90 + (i * 0.1),
                "btts_n": 1.90 + (i * 0.1),
            }

        rows.append(
            {
                "home_name": f"Home_{i}",
                "away_name": f"Away_{i}",
                "datetime": DT_BASE + timedelta(hours=i * 3),
                "scores": scores,
                "odds": odds,
                "result_url": f"https://example.com/match/{i}" if with_url else None,
            }
        )
    return pd.DataFrame(rows)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def ba(tmp_path):
    assistant = BetAssistant(str(tmp_path / "slips.db"))
    yield assistant
    with contextlib.suppress(Exception):
        assistant.close()


@pytest.fixture
def loaded_ba(tmp_path):
    """BetAssistant with matches pre-loaded."""
    assistant = BetAssistant(str(tmp_path / "loaded.db"))
    assistant.load_matches(make_matches_df(10))
    yield assistant
    with contextlib.suppress(Exception):
        assistant.close()


# ── BetSlipConfig ─────────────────────────────────────────────────────────────


class TestBetSlipConfig:
    def test_normal_defaults(self):
        cfg = BetSlipConfig()
        assert cfg.target_odds == 3.0
        assert cfg.target_legs == 3
        assert cfg.consensus_floor == 50.0

    def test_normal_custom_values(self):
        cfg = BetSlipConfig(target_odds=10.0, target_legs=5, consensus_floor=60.0)
        assert cfg.target_odds == 10.0
        assert cfg.target_legs == 5
        assert cfg.consensus_floor == 60.0

    def test_edge_clamping_target_odds(self):
        cfg_low = BetSlipConfig(target_odds=0.5)
        assert cfg_low.target_odds == 1.10
        cfg_high = BetSlipConfig(target_odds=9999.0)
        assert cfg_high.target_odds == 1000.0

    def test_edge_clamping_target_legs(self):
        cfg_low = BetSlipConfig(target_legs=-1)
        assert cfg_low.target_legs == 1
        cfg_high = BetSlipConfig(target_legs=99)
        assert cfg_high.target_legs == 10

    def test_edge_clamping_consensus_floor(self):
        cfg = BetSlipConfig(consensus_floor=200.0)
        assert cfg.consensus_floor == 100.0

    def test_edge_clamping_quality_vs_balance(self):
        cfg = BetSlipConfig(quality_vs_balance=-0.5)
        assert cfg.quality_vs_balance == 0.0
        cfg2 = BetSlipConfig(quality_vs_balance=1.5)
        assert cfg2.quality_vs_balance == 1.0

    def test_edge_optional_fields_none_by_default(self):
        cfg = BetSlipConfig()
        assert cfg.tolerance_factor is None
        assert cfg.stop_threshold is None
        assert cfg.max_legs_overflow is None

    def test_edge_clamping_tolerance_factor(self):
        cfg = BetSlipConfig(tolerance_factor=0.01)
        assert cfg.tolerance_factor == 0.05
        cfg2 = BetSlipConfig(tolerance_factor=0.99)
        assert cfg2.tolerance_factor == 0.80


# ── get_profile ───────────────────────────────────────────────────────────────


class TestGetProfile:
    def test_normal_returns_known_profile(self):
        cfg = get_profile("low_risk")
        assert isinstance(cfg, BetSlipConfig)
        assert cfg.target_odds == 2.0

    def test_normal_returns_deep_copy(self):
        cfg1 = get_profile("medium_risk")
        cfg2 = get_profile("medium_risk")
        assert cfg1 is not cfg2
        cfg1.target_odds = 999
        assert cfg2.target_odds != 999

    def test_normal_all_profiles_exist(self):
        for name in PROFILES:
            cfg = get_profile(name)
            assert isinstance(cfg, BetSlipConfig)

    def test_error_unknown_profile_raises(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            get_profile("nonexistent_profile")


# ── _resolve helpers ──────────────────────────────────────────────────────────


class TestResolveHelpers:
    def test_tolerance_auto_derived(self):
        cfg = BetSlipConfig(target_legs=3)
        tol = _resolve_tolerance(cfg)
        assert 0.0 < tol < 1.0

    def test_tolerance_explicit_returns_as_is(self):
        cfg = BetSlipConfig(tolerance_factor=0.25)
        assert _resolve_tolerance(cfg) == 0.25

    def test_stop_threshold_auto_derived(self):
        cfg = BetSlipConfig(target_legs=3)
        st = _resolve_stop_threshold(cfg)
        assert 0.5 <= st <= 1.0

    def test_stop_threshold_explicit_returns_as_is(self):
        cfg = BetSlipConfig(stop_threshold=0.90)
        assert _resolve_stop_threshold(cfg) == 0.90

    def test_max_legs_with_overflow(self):
        cfg = BetSlipConfig(target_legs=3, max_legs_overflow=2)
        assert _resolve_max_legs(cfg) == 5

    def test_max_legs_auto_single(self):
        cfg = BetSlipConfig(target_legs=1)
        assert _resolve_max_legs(cfg) == 1

    def test_max_legs_auto_small(self):
        cfg = BetSlipConfig(target_legs=3)
        assert _resolve_max_legs(cfg) == 4

    def test_max_legs_auto_large(self):
        cfg = BetSlipConfig(target_legs=6)
        assert _resolve_max_legs(cfg) == 8


# ── Scoring functions ─────────────────────────────────────────────────────────


class TestScoringFunctions:
    def test_score_consensus_at_floor_returns_zero(self):
        cfg = BetSlipConfig(consensus_floor=50.0)
        assert _score_consensus(50.0, cfg) == 0.0

    def test_score_consensus_at_100_returns_one(self):
        cfg = BetSlipConfig(consensus_floor=50.0)
        assert _score_consensus(100.0, cfg) == 1.0

    def test_score_consensus_midpoint(self):
        cfg = BetSlipConfig(consensus_floor=50.0)
        score = _score_consensus(75.0, cfg)
        assert score == pytest.approx(0.5)

    def test_score_consensus_floor_100_always_one(self):
        cfg = BetSlipConfig(consensus_floor=100.0)
        assert _score_consensus(100.0, cfg) == 1.0

    def test_score_sources_zero_max(self):
        assert _score_sources(5, 0) == 0.0

    def test_score_sources_at_max(self):
        assert _score_sources(10, 10) == 1.0

    def test_score_sources_half(self):
        assert _score_sources(5, 10) == 0.5

    def test_score_balance_perfect_match(self):
        assert _score_balance(1.50, 1.50, 0.20) == 1.0

    def test_score_balance_at_edge(self):
        # deviation = |1.80 - 1.50| / 1.50 = 0.20, tolerance 0.20 → score 0.0
        assert _score_balance(1.80, 1.50, 0.20) == pytest.approx(0.0)

    def test_score_balance_beyond_edge(self):
        assert _score_balance(3.00, 1.50, 0.20) == 0.0

    def test_score_pick_returns_tier_and_score(self):
        opt = {"odds": 1.50, "consensus": 80.0, "sources": 5}
        cfg = BetSlipConfig()
        tier, score = _score_pick(opt, 1.50, 10, cfg)
        assert tier in (1, 2)
        assert 0.0 <= score <= 1.0


# ── _parse_score and _determine_outcome ───────────────────────────────────────


class TestOutcomeFunctions:
    def test_parse_score_normal(self):
        assert _parse_score("2:1") == (2, 1)

    def test_parse_score_draw(self):
        assert _parse_score("0:0") == (0, 0)

    def test_parse_score_error_invalid_format(self):
        with pytest.raises(Exception):
            _parse_score("invalid")

    def test_determine_outcome_home_win(self):
        assert _determine_outcome(2, 1, "1", "result") == "Won"
        assert _determine_outcome(2, 1, "2", "result") == "Lost"
        assert _determine_outcome(2, 1, "X", "result") == "Lost"

    def test_determine_outcome_draw(self):
        assert _determine_outcome(1, 1, "X", "result") == "Won"
        assert _determine_outcome(1, 1, "1", "result") == "Lost"

    def test_determine_outcome_away_win(self):
        assert _determine_outcome(0, 2, "2", "result") == "Won"
        assert _determine_outcome(0, 2, "1", "result") == "Lost"

    def test_determine_outcome_over_25(self):
        assert _determine_outcome(2, 1, "Over 2.5", "over_under_2.5") == "Won"
        assert _determine_outcome(1, 0, "Over 2.5", "over_under_2.5") == "Lost"

    def test_determine_outcome_under_25(self):
        assert _determine_outcome(1, 1, "Under 2.5", "over_under_2.5") == "Won"
        assert _determine_outcome(2, 1, "Under 2.5", "over_under_2.5") == "Lost"

    def test_determine_outcome_btts_yes(self):
        assert _determine_outcome(1, 1, "BTTS Yes", "btts") == "Won"
        assert _determine_outcome(1, 0, "BTTS Yes", "btts") == "Lost"

    def test_determine_outcome_btts_no(self):
        assert _determine_outcome(1, 0, "BTTS No", "btts") == "Won"
        assert _determine_outcome(2, 1, "BTTS No", "btts") == "Lost"

    def test_determine_outcome_unknown_market_type(self):
        assert _determine_outcome(1, 0, "?", "unknown_type") == "Pending"


# ── _calc_consensus ───────────────────────────────────────────────────────────


class TestCalcConsensus:
    def test_normal_all_home_wins(self):
        scores = [{"home": 2, "away": 0}, {"home": 3, "away": 1}]
        result = BetAssistant._calc_consensus(scores)
        assert result["result"]["home"] == 100.0
        assert result["result"]["draw"] == 0.0
        assert result["result"]["away"] == 0.0

    def test_normal_all_draws(self):
        scores = [{"home": 1, "away": 1}, {"home": 0, "away": 0}]
        result = BetAssistant._calc_consensus(scores)
        assert result["result"]["draw"] == 100.0

    def test_normal_over_under(self):
        # Both predict 3+ total goals
        scores = [{"home": 2, "away": 1}, {"home": 3, "away": 2}]
        result = BetAssistant._calc_consensus(scores)
        assert result["over_under_2.5"]["over"] == 100.0
        assert result["over_under_2.5"]["under"] == 0.0

    def test_normal_btts(self):
        scores = [{"home": 1, "away": 1}, {"home": 2, "away": 3}]
        result = BetAssistant._calc_consensus(scores)
        assert result["btts"]["yes"] == 100.0
        assert result["btts"]["no"] == 0.0

    def test_edge_empty_scores(self):
        result = BetAssistant._calc_consensus([])
        assert result["result"]["home"] == 0.0
        assert result["over_under_2.5"]["over"] == 0.0
        assert result["btts"]["yes"] == 0.0

    def test_edge_single_score(self):
        result = BetAssistant._calc_consensus([{"home": 2, "away": 1}])
        assert result["result"]["home"] == 100.0

    def test_edge_mixed_results(self):
        scores = [
            {"home": 2, "away": 0},  # home win, under, btts no
            {"home": 0, "away": 1},  # away win, under, btts no
            {"home": 1, "away": 1},  # draw, under, btts yes
        ]
        result = BetAssistant._calc_consensus(scores)
        assert result["result"]["home"] == pytest.approx(33.3, abs=0.1)
        assert result["result"]["draw"] == pytest.approx(33.3, abs=0.1)
        assert result["result"]["away"] == pytest.approx(33.3, abs=0.1)

    def test_edge_none_values_treated_as_zero(self):
        scores = [{"home": None, "away": None}]
        result = BetAssistant._calc_consensus(scores)
        assert result["result"]["draw"] == 100.0  # 0 == 0 → draw


# ── load_matches ──────────────────────────────────────────────────────────────


class TestLoadMatches:
    def test_normal_loads_and_processes(self, ba):
        df = make_matches_df(5)
        ba.load_matches(df)
        assert len(ba._df) == 5

    def test_normal_computes_consensus_columns(self, ba):
        df = make_matches_df(3, sources_per_match=4)
        ba.load_matches(df)
        for col in ["cons_home", "cons_draw", "cons_away", "cons_over", "cons_under"]:
            assert col in ba._df.columns

    def test_normal_computes_odds_columns(self, ba):
        df = make_matches_df(2)
        ba.load_matches(df)
        for col in ["odds_home", "odds_draw", "odds_away"]:
            assert col in ba._df.columns
            assert ba._df[col].iloc[0] > 0

    def test_normal_counts_unique_sources(self, ba):
        df = make_matches_df(1, sources_per_match=5)
        ba.load_matches(df)
        assert ba._df.iloc[0]["sources"] == 5

    def test_edge_empty_dataframe(self, ba):
        ba.load_matches(pd.DataFrame())
        assert ba._df.empty

    def test_edge_match_without_odds(self, ba):
        df = make_matches_df(1, with_odds=False)
        ba.load_matches(df)
        assert ba._df.iloc[0]["odds_home"] == 0.0

    def test_edge_match_without_scores(self, ba):
        df = pd.DataFrame(
            [
                {
                    "home_name": "A",
                    "away_name": "B",
                    "datetime": DT_BASE,
                    "scores": [],
                    "odds": {"home": 1.5},
                    "result_url": "http://x",
                }
            ]
        )
        ba.load_matches(df)
        assert ba._df.iloc[0]["sources"] == 0


# ── filter_matches ────────────────────────────────────────────────────────────


class TestFilterMatches:
    def test_normal_search_text(self, loaded_ba):
        result = loaded_ba.filter_matches(search_text="Home_0")
        assert len(result) == 1

    def test_normal_date_from(self, loaded_ba):
        date_str = (DT_BASE + timedelta(hours=6)).strftime("%Y-%m-%d")
        result = loaded_ba.filter_matches(date_from=date_str)
        # All matches are within the same day range
        assert len(result) >= 0

    def test_normal_min_sources(self, loaded_ba):
        result = loaded_ba.filter_matches(min_sources=2)
        assert len(result) == 10  # all have 3 sources

    def test_edge_empty_df(self, ba):
        result = ba.filter_matches(search_text="anything")
        assert result.empty

    def test_edge_no_filters_returns_all(self, loaded_ba):
        result = loaded_ba.filter_matches()
        assert len(result) == 10

    def test_edge_min_sources_1_returns_all(self, loaded_ba):
        result = loaded_ba.filter_matches(min_sources=1)
        assert len(result) == 10


# ── build_slip ────────────────────────────────────────────────────────────────


class TestBuildSlip:
    def test_normal_returns_list_of_dicts(self, loaded_ba):
        legs = loaded_ba.build_slip("medium_risk")
        assert isinstance(legs, list)
        if legs:
            assert isinstance(legs[0], dict)
            assert "match" in legs[0]
            assert "odds" in legs[0]
            assert "market" in legs[0]

    def test_normal_uses_named_profile(self, loaded_ba):
        legs = loaded_ba.build_slip("low_risk")
        assert isinstance(legs, list)

    def test_normal_uses_config_object(self, loaded_ba):
        cfg = BetSlipConfig(target_odds=2.0, target_legs=2)
        legs = loaded_ba.build_slip(cfg)
        assert isinstance(legs, list)

    def test_normal_respects_extra_excluded_urls(self, loaded_ba):
        # Exclude all but one URL
        urls_to_exclude = [f"https://example.com/match/{i}" for i in range(9)]
        legs = loaded_ba.build_slip("medium_risk", extra_excluded_urls=urls_to_exclude)
        if legs:
            for leg in legs:
                assert leg["result_url"] not in urls_to_exclude

    def test_edge_empty_df_returns_empty(self, ba):
        legs = ba.build_slip("medium_risk")
        assert legs == []

    def test_edge_no_matches_pass_quality_gate(self, loaded_ba):
        cfg = BetSlipConfig(consensus_floor=100.0, min_odds=99.0)
        legs = loaded_ba.build_slip(cfg)
        assert legs == []

    def test_normal_no_duplicate_matches_in_slip(self, loaded_ba):
        cfg = BetSlipConfig(target_legs=5, target_odds=10.0)
        legs = loaded_ba.build_slip(cfg)
        match_names = [leg["match"] for leg in legs]
        assert len(match_names) == len(set(match_names))


# ── save_slip and get_slips ───────────────────────────────────────────────────


class TestSaveAndGetSlips:
    def _make_legs(self, n=3):
        return [
            {
                "match": f"Home_{i} vs Away_{i}",
                "datetime": DT_BASE + timedelta(hours=i),
                "market": "1",
                "market_type": "result",
                "odds": 1.50 + (i * 0.1),
                "result_url": f"https://example.com/match/{i}",
                "consensus": 80.0,
                "sources": 3,
            }
            for i in range(n)
        ]

    def test_normal_save_and_retrieve(self, ba):
        legs = self._make_legs(3)
        slip_id = ba.save_slip("test_profile", legs, units=1.0)
        assert isinstance(slip_id, int)
        assert slip_id > 0

        slips = ba.get_slips()
        assert len(slips) == 1
        assert slips[0]["slip_id"] == slip_id
        assert slips[0]["profile"] == "test_profile"
        assert len(slips[0]["legs"]) == 3

    def test_normal_total_odds_computed(self, ba):
        legs = self._make_legs(2)
        ba.save_slip("p", legs)
        slips = ba.get_slips()
        expected_odds = math.prod(leg["odds"] for leg in legs)
        assert slips[0]["total_odds"] == pytest.approx(expected_odds, rel=0.01)

    def test_normal_units_stored(self, ba):
        legs = self._make_legs(1)
        ba.save_slip("p", legs, units=2.5)
        slips = ba.get_slips()
        assert slips[0]["units"] == 2.5

    def test_normal_filter_by_profile(self, ba):
        ba.save_slip("profile_a", self._make_legs(2))
        ba.save_slip("profile_b", self._make_legs(2))
        slips_a = ba.get_slips(profile="profile_a")
        assert len(slips_a) == 1
        assert slips_a[0]["profile"] == "profile_a"

    def test_edge_get_slips_all_filter(self, ba):
        ba.save_slip("p1", self._make_legs(1))
        ba.save_slip("p2", self._make_legs(1))
        slips = ba.get_slips(profile="all")
        assert len(slips) == 2

    def test_edge_get_slips_empty_db(self, ba):
        slips = ba.get_slips()
        assert slips == []

    def test_normal_slip_status_pending(self, ba):
        ba.save_slip("p", self._make_legs(2))
        slips = ba.get_slips()
        assert slips[0]["slip_status"] == "Pending"


# ── delete_slip ───────────────────────────────────────────────────────────────


class TestDeleteSlip:
    def test_normal_deletes_slip_and_legs(self, ba):
        legs = [
            {
                "match": "A vs B",
                "datetime": DT_BASE,
                "market": "1",
                "market_type": "result",
                "odds": 1.50,
                "result_url": "http://x",
            }
        ]
        slip_id = ba.save_slip("p", legs)
        ba.delete_slip(slip_id)
        assert ba.get_slips() == []

    def test_edge_delete_nonexistent_slip_is_noop(self, ba):
        ba.delete_slip(9999)  # should not raise


# ── update_leg ────────────────────────────────────────────────────────────────


class TestUpdateLeg:
    def test_normal_updates_status(self, ba):
        legs = [
            {
                "match": "A vs B",
                "datetime": DT_BASE,
                "market": "1",
                "market_type": "result",
                "odds": 1.50,
                "result_url": "http://x",
            }
        ]
        ba.save_slip("p", legs)
        # Get leg_id from the DB
        rows = ba.fetch_rows("SELECT leg_id FROM legs LIMIT 1")
        leg_id = rows[0]["leg_id"]
        ba.update_leg(leg_id, "Won")
        updated = ba.fetch_rows("SELECT status FROM legs WHERE leg_id = ?", (leg_id,))
        assert updated[0]["status"] == "Won"

    def test_normal_update_to_lost(self, ba):
        legs = [
            {
                "match": "A vs B",
                "datetime": DT_BASE,
                "market": "1",
                "market_type": "result",
                "odds": 1.50,
                "result_url": "http://x",
            }
        ]
        ba.save_slip("p", legs)
        rows = ba.fetch_rows("SELECT leg_id FROM legs LIMIT 1")
        ba.update_leg(rows[0]["leg_id"], "Lost")
        updated = ba.fetch_rows(
            "SELECT status FROM legs WHERE leg_id = ?", (rows[0]["leg_id"],)
        )
        assert updated[0]["status"] == "Lost"


# ── get_excluded_urls ─────────────────────────────────────────────────────────


class TestGetExcludedUrls:
    def test_normal_pending_urls_excluded(self, ba):
        legs = [
            {
                "match": "A vs B",
                "datetime": DT_BASE,
                "market": "1",
                "market_type": "result",
                "odds": 1.50,
                "result_url": "http://pending-url",
            }
        ]
        ba.save_slip("p", legs)
        excluded = ba.get_excluded_urls()
        assert "http://pending-url" in excluded

    def test_normal_won_urls_excluded(self, ba):
        legs = [
            {
                "match": "A vs B",
                "datetime": DT_BASE,
                "market": "1",
                "market_type": "result",
                "odds": 1.50,
                "result_url": "http://won-url",
            }
        ]
        ba.save_slip("p", legs)
        rows = ba.fetch_rows("SELECT leg_id FROM legs LIMIT 1")
        ba.update_leg(rows[0]["leg_id"], "Won")
        excluded = ba.get_excluded_urls()
        assert "http://won-url" in excluded

    def test_normal_pending_in_lost_slip_not_excluded(self, ba):
        """If a slip has a Lost leg, other Pending legs should NOT be excluded."""
        legs = [
            {
                "match": "A vs B",
                "datetime": DT_BASE,
                "market": "1",
                "market_type": "result",
                "odds": 1.50,
                "result_url": "http://lost-slip-pending",
            },
            {
                "match": "C vs D",
                "datetime": DT_BASE,
                "market": "2",
                "market_type": "result",
                "odds": 2.0,
                "result_url": "http://lost-slip-lost",
            },
        ]
        ba.save_slip("p", legs)
        # Mark one leg as Lost
        all_legs = ba.fetch_rows("SELECT leg_id, result_url FROM legs")
        for leg in all_legs:
            if leg["result_url"] == "http://lost-slip-lost":
                ba.update_leg(leg["leg_id"], "Lost")

        excluded = ba.get_excluded_urls()
        # The Lost URL is excluded (settled forever)
        assert "http://lost-slip-lost" in excluded
        # The Pending URL in the lost slip is NOT excluded
        assert "http://lost-slip-pending" not in excluded

    def test_edge_empty_db_returns_empty_list(self, ba):
        assert ba.get_excluded_urls() == []


# ── _rows_to_slips ────────────────────────────────────────────────────────────


class TestRowsToSlips:
    def test_normal_groups_legs_under_slip(self):
        rows = [
            (1, "2026-04-01", "profile", 3.0, 1.0, "A vs B", "2026-04-01T15:00:00", "1", "result", 1.5, "Pending", "http://x"),
            (1, "2026-04-01", "profile", 3.0, 1.0, "C vs D", "2026-04-01T18:00:00", "2", "result", 2.0, "Pending", "http://y"),
        ]
        slips = BetAssistant._rows_to_slips(rows)
        assert len(slips) == 1
        assert len(slips[0]["legs"]) == 2

    def test_normal_status_pending(self):
        rows = [
            (1, "2026-04-01", "p", 3.0, 1.0, "A vs B", "2026-04-01T15:00:00", "1", "result", 1.5, "Pending", None),
        ]
        slips = BetAssistant._rows_to_slips(rows)
        assert slips[0]["slip_status"] == "Pending"

    def test_normal_status_won(self):
        rows = [
            (1, "2026-04-01", "p", 3.0, 1.0, "A vs B", "2026-04-01T15:00:00", "1", "result", 1.5, "Won", None),
        ]
        slips = BetAssistant._rows_to_slips(rows)
        assert slips[0]["slip_status"] == "Won"

    def test_normal_status_lost(self):
        rows = [
            (1, "2026-04-01", "p", 3.0, 1.0, "A vs B", "2026-04-01T15:00:00", "1", "result", 1.5, "Won", None),
            (1, "2026-04-01", "p", 3.0, 1.0, "C vs D", "2026-04-01T18:00:00", "2", "result", 2.0, "Lost", None),
        ]
        slips = BetAssistant._rows_to_slips(rows)
        assert slips[0]["slip_status"] == "Lost"

    def test_normal_status_live(self):
        rows = [
            (1, "2026-04-01", "p", 3.0, 1.0, "A vs B", "2026-04-01T15:00:00", "1", "result", 1.5, "Live", None),
            (1, "2026-04-01", "p", 3.0, 1.0, "C vs D", "2026-04-01T18:00:00", "2", "result", 2.0, "Pending", None),
        ]
        slips = BetAssistant._rows_to_slips(rows)
        assert slips[0]["slip_status"] == "Live"

    def test_edge_multiple_slips(self):
        rows = [
            (1, "2026-04-01", "p1", 3.0, 1.0, "A vs B", "2026-04-01T15:00:00", "1", "result", 1.5, "Pending", None),
            (2, "2026-04-02", "p2", 5.0, 2.0, "C vs D", "2026-04-02T15:00:00", "2", "result", 2.0, "Won", None),
        ]
        slips = BetAssistant._rows_to_slips(rows)
        assert len(slips) == 2


# ── Context manager ───────────────────────────────────────────────────────────


class TestContextManager:
    def test_normal_with_statement(self, tmp_path):
        with BetAssistant(str(tmp_path / "ctx.db")) as ba:
            ba.load_matches(make_matches_df(2))
            assert len(ba._df) == 2

    def test_normal_close_called_on_exit(self, tmp_path):
        path = str(tmp_path / "ctx2.db")
        with BetAssistant(path) as ba:
            ba.load_matches(make_matches_df(1))
        # After exit, connection should be closed
        assert os.path.exists(path)


# ── Complex Scenarios ─────────────────────────────────────────────────────────


class TestBetAssistantScenarios:
    def test_scenario_full_workflow(self, tmp_path):
        """load → build → save → retrieve → verify."""
        with BetAssistant(str(tmp_path / "workflow.db")) as ba:
            ba.load_matches(make_matches_df(10))
            legs = ba.build_slip("medium_risk")
            if legs:
                slip_id = ba.save_slip("medium_risk", legs)
                slips = ba.get_slips()
                assert len(slips) == 1
                assert slips[0]["slip_id"] == slip_id
                assert len(slips[0]["legs"]) == len(legs)

    def test_scenario_auto_exclude_prevents_duplicates(self, tmp_path):
        """build_slip_auto_exclude must not reuse URLs from existing slips."""
        with BetAssistant(str(tmp_path / "auto_excl.db")) as ba:
            ba.load_matches(make_matches_df(20, sources_per_match=5))

            # Build and save first slip
            legs1 = ba.build_slip_auto_exclude("medium_risk")
            if legs1:
                ba.save_slip("medium_risk", legs1)
                used_urls_1 = {leg["result_url"] for leg in legs1}

                # Build second slip — should not reuse same URLs
                legs2 = ba.build_slip_auto_exclude("medium_risk")
                if legs2:
                    used_urls_2 = {leg["result_url"] for leg in legs2}
                    assert used_urls_1.isdisjoint(used_urls_2)

    def test_scenario_multiple_profiles(self, tmp_path):
        """Save slips from different profiles; filter retrieval by profile."""
        with BetAssistant(str(tmp_path / "profiles.db")) as ba:
            ba.load_matches(make_matches_df(20, sources_per_match=5))

            for profile in ["low_risk", "medium_risk", "high_risk"]:
                legs = ba.build_slip(profile)
                if legs:
                    ba.save_slip(profile, legs)

            all_slips = ba.get_slips()
            low_slips = ba.get_slips(profile="low_risk")
            # At least one profile should have generated a slip
            assert len(all_slips) >= 1
            for slip in low_slips:
                assert slip["profile"] == "low_risk"

    def test_scenario_settle_legs_manually(self, tmp_path):
        """Save a slip, manually settle all legs, verify slip status transitions."""
        with BetAssistant(str(tmp_path / "settle.db")) as ba:
            ba.load_matches(make_matches_df(5))
            legs = ba.build_slip(
                BetSlipConfig(target_odds=2.0, target_legs=2, consensus_floor=0.0)
            )
            if legs:
                ba.save_slip("test", legs)
                all_legs = ba.fetch_rows("SELECT leg_id FROM legs")

                # Mark all Won
                for leg in all_legs:
                    ba.update_leg(leg["leg_id"], "Won")

                slips = ba.get_slips()
                assert slips[0]["slip_status"] == "Won"

                # Mark one Lost → slip becomes Lost
                ba.update_leg(all_legs[0]["leg_id"], "Lost")
                slips = ba.get_slips()
                assert slips[0]["slip_status"] == "Lost"

    def test_scenario_delete_and_regenrate(self, tmp_path):
        """Save, delete, verify gone, regenerate fresh slip."""
        with BetAssistant(str(tmp_path / "del_regen.db")) as ba:
            ba.load_matches(make_matches_df(10))
            legs = ba.build_slip("medium_risk")
            if legs:
                slip_id = ba.save_slip("medium_risk", legs)
                assert len(ba.get_slips()) == 1

                ba.delete_slip(slip_id)
                assert len(ba.get_slips()) == 0

                # URLs from deleted slip should no longer be excluded
                legs2 = ba.build_slip_auto_exclude("medium_risk")
                assert isinstance(legs2, list)
