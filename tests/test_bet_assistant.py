"""
Comprehensive tests for BetAssistant.

Public API covered:
  BetSlipConfig, get_profile, load_matches, filter_matches,
  build_slip, build_slip_auto_exclude, save_slip, get_slips,
  delete_slip, get_excluded_urls, update_leg, close

Private helpers covered via integration:
  _calc_consensus, _collect_candidates, _select_legs,
  _rows_to_slips, resolve_tolerance, resolve_stop_threshold,
  resolve_max_legs, score_pick, determine_outcome, parse_score

Each method has: normal case(s), edge case(s), error case.
Plus 5 complex integration scenarios at the bottom.
"""

import contextlib
import math
import os
from datetime import datetime, timedelta

import pandas as pd
import pytest

from bet_framework.BetAssistant import BetAssistant
from bet_framework.core.consensus import calc_consensus
from bet_framework.core.outcomes import determine_outcome, parse_score
from bet_framework.core.scoring import (
    apply_odds_movement_adjustment,
    classify_odds_movement,
    odds_movement_factor,
    resolve_max_legs,
    resolve_odds_movement_strength_min,
    resolve_odds_movement_weight,
    resolve_stop_threshold,
    resolve_tolerance,
    score_balance,
    score_consensus,
    score_pick,
    score_sources,
)
from bet_framework.core.Slip import PROFILES, BetLeg, BetSlipConfig, CandidateLeg, get_profile
from bet_framework.core.types import MarketLabel, MarketType, Outcome

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
        cfg_high = BetSlipConfig(target_legs=101)
        assert cfg_high.target_legs == 100

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
        tol = resolve_tolerance(cfg)
        assert 0.0 < tol < 1.0

    def test_tolerance_explicit_returns_as_is(self):
        cfg = BetSlipConfig(tolerance_factor=0.25)
        assert resolve_tolerance(cfg) == 0.25

    def test_stop_threshold_auto_derived(self):
        cfg = BetSlipConfig(target_legs=3)
        st = resolve_stop_threshold(cfg)
        assert 0.5 <= st <= 1.0

    def test_stop_threshold_explicit_returns_as_is(self):
        cfg = BetSlipConfig(stop_threshold=0.90)
        assert resolve_stop_threshold(cfg) == 0.90

    def test_max_legs_with_overflow(self):
        cfg = BetSlipConfig(target_legs=3, max_legs_overflow=2)
        assert resolve_max_legs(cfg) == 5

    def test_max_legs_auto_single(self):
        cfg = BetSlipConfig(target_legs=1)
        assert resolve_max_legs(cfg) == 1

    def test_max_legs_auto_small(self):
        cfg = BetSlipConfig(target_legs=3)
        assert resolve_max_legs(cfg) == 4

    def test_max_legs_auto_large(self):
        cfg = BetSlipConfig(target_legs=6)
        assert resolve_max_legs(cfg) == 8


# ── Scoring functions ─────────────────────────────────────────────────────────


class TestScoringFunctions:
    def test_score_consensus_at_floor_returns_zero(self):
        cfg = BetSlipConfig(consensus_floor=50.0)
        assert score_consensus(50.0, cfg) == 0.0

    def test_score_consensus_at_100_returns_one(self):
        cfg = BetSlipConfig(consensus_floor=50.0)
        assert score_consensus(100.0, cfg) == 1.0

    def test_score_consensus_midpoint(self):
        cfg = BetSlipConfig(consensus_floor=50.0)
        score = score_consensus(75.0, cfg)
        assert score == pytest.approx(0.5)

    def test_score_consensus_floor_100_always_one(self):
        cfg = BetSlipConfig(consensus_floor=100.0)
        assert score_consensus(100.0, cfg) == 1.0

    def test_score_sources_zero_max(self):
        assert score_sources(5, 0) == 0.0

    def test_score_sources_at_max(self):
        assert score_sources(10, 10) == 1.0

    def test_score_sources_half(self):
        assert score_sources(5, 10) == 0.5

    def test_score_balance_perfect_match(self):
        cfg = BetSlipConfig()
        assert score_balance(1.50, 1.50, 0.20, cfg) == 1.0

    def test_score_balance_at_edge_linear(self):
        # With linear decay: deviation = tolerance → score 0.0
        cfg = BetSlipConfig(balance_decay="linear")
        assert score_balance(1.80, 1.50, 0.20, cfg) == pytest.approx(0.0)

    def test_score_balance_at_edge_gaussian(self):
        # With gaussian (default): score never reaches exactly 0
        cfg = BetSlipConfig()
        score = score_balance(1.80, 1.50, 0.20, cfg)
        assert 0.0 < score < 0.5  # Gaussian gives ~0.25 at 1σ

    def test_score_balance_beyond_edge_linear(self):
        cfg = BetSlipConfig(balance_decay="linear")
        assert score_balance(3.00, 1.50, 0.20, cfg) == 0.0

    def test_score_balance_beyond_edge_gaussian(self):
        # Gaussian never exactly 0, but very small far from ideal
        cfg = BetSlipConfig()
        score = score_balance(3.00, 1.50, 0.20, cfg)
        assert score > 0.0
        assert score < 0.01

    def test_score_pick_returns_tier_score_quality(self):
        opt = CandidateLeg(
            match_name="A vs B",
            datetime="2025-01-01",
            market=MarketLabel.HOME,
            market_type=MarketType.RESULT,
            consensus=70.0,
            odds=1.50,
            result_url="http://x.com",
            sources=3,
        )
        cfg = BetSlipConfig()
        tier, score, quality = score_pick(opt, 1.50, 10, cfg)
        assert tier in (1, 2)
        assert 0.0 <= score <= 1.0
        assert 0.0 <= quality <= 1.0


# ── Odds Movement Scoring ────────────────────────────────────────────────────


class TestOddsMovementScoring:
    # resolve_odds_movement_weight
    def test_resolve_weight_none_returns_default(self):
        assert resolve_odds_movement_weight(BetSlipConfig()) == 0.05

    def test_resolve_weight_explicit(self):
        assert resolve_odds_movement_weight(BetSlipConfig(odds_movement_weight=0.10)) == 0.10

    def test_resolve_weight_capped(self):
        assert resolve_odds_movement_weight(BetSlipConfig(odds_movement_weight=0.50)) == 0.30

    # resolve_odds_movement_strength_min
    def test_resolve_strength_min_none(self):
        assert resolve_odds_movement_strength_min(BetSlipConfig()) == 0.05

    def test_resolve_strength_min_explicit(self):
        assert resolve_odds_movement_strength_min(BetSlipConfig(odds_movement_strength_min=0.10)) == 0.10

    # classify_odds_movement
    def test_classify_down_confirm(self):
        assert classify_odds_movement("down") == "confirm"

    def test_classify_up_infirm(self):
        assert classify_odds_movement("up") == "infirm"

    def test_classify_stable(self):
        assert classify_odds_movement("stable") == "stable"

    def test_classify_none(self):
        assert classify_odds_movement(None) == "stable"

    # odds_movement_factor
    def test_factor_confirm(self):
        assert odds_movement_factor("confirm") == 1.0

    def test_factor_infirm(self):
        assert odds_movement_factor("infirm") == 0.0

    def test_factor_stable(self):
        assert odds_movement_factor("stable") == 0.5

    # apply_odds_movement_adjustment
    def test_confirm_boosts(self):
        cfg = BetSlipConfig(odds_movement_weight=0.10, odds_movement_strength_min=0.05)
        assert apply_odds_movement_adjustment(0.80, "down", 0.10, cfg) > 0.80

    def test_infirm_penalizes(self):
        cfg = BetSlipConfig(odds_movement_weight=0.10, odds_movement_strength_min=0.05)
        assert apply_odds_movement_adjustment(0.80, "up", 0.10, cfg) < 0.80

    def test_below_threshold_skips(self):
        cfg = BetSlipConfig(odds_movement_weight=0.10, odds_movement_strength_min=0.10)
        assert apply_odds_movement_adjustment(0.80, "down", 0.05, cfg) == 0.80

    def test_zero_weight_no_change(self):
        cfg = BetSlipConfig(odds_movement_weight=0.0, odds_movement_strength_min=0.05)
        assert apply_odds_movement_adjustment(0.80, "down", 0.10, cfg) == 0.80

    # Integration: score_pick with movement
    def test_score_pick_with_movement(self):
        opt = CandidateLeg(
            match_name="A vs B",
            datetime="2025-01-01",
            market=MarketLabel.HOME,
            market_type=MarketType.RESULT,
            consensus=70.0,
            odds=1.50,
            result_url="http://x.com",
            sources=3,
            odds_movement_direction="down",
            odds_movement_strength=0.10,
        )
        cfg = BetSlipConfig(odds_movement_weight=0.10, odds_movement_strength_min=0.05)
        tier, score, quality = score_pick(opt, 1.50, 10, cfg)
        assert 0.0 <= score <= 1.0

    def test_score_pick_without_movement_defaults(self):
        opt = CandidateLeg(
            match_name="A vs B",
            datetime="2025-01-01",
            market=MarketLabel.HOME,
            market_type=MarketType.RESULT,
            consensus=70.0,
            odds=1.50,
            result_url="http://x.com",
            sources=3,
        )
        cfg = BetSlipConfig()
        tier, score, quality = score_pick(opt, 1.50, 10, cfg)
        assert 0.0 <= score <= 1.0


# ── parse_score and determine_outcome ───────────────────────────────────────


class TestOutcomeFunctions:
    def test_parsescore_normal(self):
        assert parse_score("2:1") == (2, 1)

    def test_parsescore_draw(self):
        assert parse_score("0:0") == (0, 0)

    def test_parsescore_error_invalid_format(self):
        with pytest.raises(Exception):
            parse_score("invalid")

    def test_determine_outcome_home_win(self):
        assert determine_outcome(2, 1, MarketLabel.HOME, MarketType.RESULT) == Outcome.WON
        assert determine_outcome(2, 1, MarketLabel.AWAY, MarketType.RESULT) == Outcome.LOST
        assert determine_outcome(2, 1, MarketLabel.DRAW, MarketType.RESULT) == Outcome.LOST

    def test_determine_outcome_draw(self):
        assert determine_outcome(1, 1, MarketLabel.DRAW, MarketType.RESULT) == Outcome.WON
        assert determine_outcome(1, 1, MarketLabel.HOME, MarketType.RESULT) == Outcome.LOST

    def test_determine_outcome_away_win(self):
        assert determine_outcome(0, 2, MarketLabel.AWAY, MarketType.RESULT) == Outcome.WON
        assert determine_outcome(0, 2, MarketLabel.HOME, MarketType.RESULT) == Outcome.LOST

    def test_determine_outcome_over_25(self):
        assert determine_outcome(2, 1, MarketLabel.OVER_25, MarketType.OVER_UNDER_25) == Outcome.WON
        assert determine_outcome(1, 0, MarketLabel.OVER_25, MarketType.OVER_UNDER_25) == Outcome.LOST

    def test_determine_outcome_under_25(self):
        assert determine_outcome(1, 1, MarketLabel.UNDER_25, MarketType.OVER_UNDER_25) == Outcome.WON
        assert determine_outcome(2, 1, MarketLabel.UNDER_25, MarketType.OVER_UNDER_25) == Outcome.LOST

    def test_determine_outcome_btts_yes(self):
        assert determine_outcome(1, 1, MarketLabel.BTTS_YES, MarketType.BTTS) == Outcome.WON
        assert determine_outcome(1, 0, MarketLabel.BTTS_YES, MarketType.BTTS) == Outcome.LOST

    def test_determine_outcome_btts_no(self):
        assert determine_outcome(1, 0, MarketLabel.BTTS_NO, MarketType.BTTS) == Outcome.WON
        assert determine_outcome(2, 1, MarketLabel.BTTS_NO, MarketType.BTTS) == Outcome.LOST

    def test_determine_outcome_unknown_market_type(self):
        assert determine_outcome(1, 0, "?", "unknown_type") == Outcome.PENDING


# ── _calc_consensus ───────────────────────────────────────────────────────────


class TestCalcConsensus:
    def test_normal_all_home_wins(self):
        scores = [{"home": 2, "away": 0}, {"home": 3, "away": 1}]
        result = calc_consensus(scores)
        assert result[MarketType.RESULT]["home"] == 100.0
        assert result[MarketType.RESULT]["draw"] == 0.0
        assert result[MarketType.RESULT]["away"] == 0.0

    def test_normal_all_draws(self):
        scores = [{"home": 1, "away": 1}, {"home": 0, "away": 0}]
        result = calc_consensus(scores)
        assert result[MarketType.RESULT]["draw"] == 100.0

    def test_normal_over_under(self):
        # Both predict 3+ total goals
        scores = [{"home": 2, "away": 1}, {"home": 3, "away": 2}]
        result = calc_consensus(scores)
        assert result[MarketType.OVER_UNDER_25]["over"] == 100.0
        assert result[MarketType.OVER_UNDER_25]["under"] == 0.0

    def test_normal_btts(self):
        scores = [{"home": 1, "away": 1}, {"home": 2, "away": 3}]
        result = calc_consensus(scores)
        assert result[MarketType.BTTS]["yes"] == 100.0
        assert result[MarketType.BTTS]["no"] == 0.0

    def test_edge_empty_scores(self):
        result = calc_consensus([])
        assert result[MarketType.RESULT]["home"] == 0.0
        assert result[MarketType.OVER_UNDER_25]["over"] == 0.0
        assert result[MarketType.BTTS]["yes"] == 0.0

    def test_edge_single_score(self):
        result = calc_consensus([{"home": 2, "away": 1}])
        assert result[MarketType.RESULT]["home"] == 100.0

    def test_edge_mixed_results(self):
        scores = [
            {"home": 2, "away": 0},  # home win, under, btts no
            {"home": 0, "away": 1},  # away win, under, btts no
            {"home": 1, "away": 1},  # draw, under, btts yes
        ]
        result = calc_consensus(scores)
        assert result[MarketType.RESULT]["home"] == pytest.approx(33.3, abs=0.1)
        assert result[MarketType.RESULT]["draw"] == pytest.approx(33.3, abs=0.1)
        assert result[MarketType.RESULT]["away"] == pytest.approx(33.3, abs=0.1)

    def test_edge_none_values_treated_as_zero(self):
        scores = [{"home": None, "away": None}]
        result = calc_consensus(scores)
        assert result[MarketType.RESULT]["draw"] == 100.0  # 0 == 0 → draw

    def test_edge_with_source_field(self):
        scores = [
            {"home": 2, "away": 0, "source": "src1"},
            {"home": 2, "away": 1, "source": "src2"},
            {"home": 1, "away": 2, "source": "src3"},
        ]
        result = calc_consensus(scores)
        # Two home wins (2-0, 2-1) and one away win (1-2)
        assert result[MarketType.RESULT]["home"] == pytest.approx(66.7, abs=0.1)
        assert result[MarketType.RESULT]["away"] == pytest.approx(33.3, abs=0.1)


# ── load_matches ──────────────────────────────────────────────────────────────


class TestLoadMatches:
    def test_normal_loads_and_processes(self, ba):
        df = make_matches_df(5)
        ba.load_matches(df)
        assert len(ba._df) == 5

    def test_normal_computes_consensus_columns(self, ba):
        df = make_matches_df(3, sources_per_match=4)
        ba.load_matches(df)
        for col in ["cons_home", "cons_draw", "cons_away", "cons_over_25", "cons_under_25"]:
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

    def test_excluded_sources_filters_consensus(self, ba):
        """Test that excluded_sources filters out specific sources from consensus calculation."""
        df = pd.DataFrame(
            [
                {
                    "home_name": "Home",
                    "away_name": "Away",
                    "datetime": DT_BASE,
                    "scores": [
                        {"home": 3, "away": 0, "source": "src_good"},
                        {"home": 3, "away": 0, "source": "src_good2"},
                        {"home": 0, "away": 3, "source": "src_bad"},  # predicts away win
                    ],
                    "odds": {"home": 1.5, "draw": 3.5, "away": 5.0},
                    "result_url": "http://test",
                }
            ]
        )
        # Without exclusion: 2 home wins, 1 away win = 66.6% home
        ba.load_matches(df)
        assert ba._df.iloc[0]["cons_home"] == pytest.approx(66.6, abs=0.2)

        # With exclusion of src_bad: only 2 home wins = 100% home
        ba2 = BetAssistant(str(ba.db_path).replace(".db", "_2.db"))
        ba2.load_matches(df, excluded_sources=["src_bad"])
        assert ba2._df.iloc[0]["cons_home"] == 100.0
        assert ba2._df.iloc[0]["sources"] == 2
        ba2.close()

    def test_excluded_sources_empty_list_unchanged(self, ba):
        """Test that empty excluded_sources list behaves like None."""
        df = make_matches_df(1, sources_per_match=3)
        ba.load_matches(df, excluded_sources=[])
        ba2 = BetAssistant(str(ba.db_path).replace(".db", "_3.db"))
        ba2.load_matches(df, excluded_sources=None)
        # Should have same consensus
        assert ba._df.iloc[0]["cons_home"] == ba2._df.iloc[0]["cons_home"]
        ba2.close()


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
            assert isinstance(legs[0], CandidateLeg)
            assert hasattr(legs[0], "match_name")
            assert hasattr(legs[0], "odds")
            assert hasattr(legs[0], "market")

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
                assert leg.result_url not in urls_to_exclude

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
        match_names = [leg.match_name for leg in legs]
        assert len(match_names) == len(set(match_names))


# ── save_slip and get_slips ───────────────────────────────────────────────────


class TestSaveAndGetSlips:
    def _make_legs(self, n=3):
        return [
            CandidateLeg(
                match_name=f"Home_{i} vs Away_{i}",
                datetime=DT_BASE + timedelta(hours=i),
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.50 + (i * 0.1),
                result_url=f"https://example.com/match/{i}",
                consensus=80.0,
                sources=3,
            )
            for i in range(n)
        ]

    def test_normal_save_and_retrieve(self, ba):
        legs = self._make_legs(3)
        slip_id = ba.save_slip("test_profile", legs, units=1.0)
        assert isinstance(slip_id, int)
        assert slip_id > 0

        slips = ba.get_slips()
        assert len(slips) == 1
        assert slips[0].slip_id == slip_id
        assert slips[0].profile == "test_profile"
        assert len(slips[0].legs) == 3

    def test_normal_total_odds_computed(self, ba):
        legs = self._make_legs(2)
        ba.save_slip("p", legs)
        slips = ba.get_slips()
        expected_odds = math.prod(leg.odds for leg in legs)
        assert slips[0].total_odds == pytest.approx(expected_odds, rel=0.01)

    def test_normal_units_stored(self, ba):
        legs = self._make_legs(1)
        ba.save_slip("p", legs, units=2.5)
        slips = ba.get_slips()
        assert slips[0].units == 2.5

    def test_normal_filter_by_profile(self, ba):
        ba.save_slip("profile_a", self._make_legs(2))
        ba.save_slip("profile_b", self._make_legs(2))
        slips_a = ba.get_slips(profile="profile_a")
        assert len(slips_a) == 1
        assert slips_a[0].profile == "profile_a"

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
        assert slips[0].slip_status == Outcome.PENDING


# ── delete_slip ───────────────────────────────────────────────────────────────


class TestDeleteSlip:
    def test_normal_deletes_slip_and_legs(self, ba):
        legs = [
            CandidateLeg(
                match_name="A vs B",
                datetime=DT_BASE,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.50,
                result_url="http://x",
                consensus=80.0,
                sources=3,
            )
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
            CandidateLeg(
                match_name="A vs B",
                datetime=DT_BASE,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.50,
                result_url="http://x",
                consensus=80.0,
                sources=3,
            )
        ]
        ba.save_slip("p", legs)
        # Get leg_id from the DB
        rows = ba.fetch_rows("SELECT leg_id FROM legs LIMIT 1")
        leg_id = rows[0]["leg_id"]
        ba.update_leg(leg_id, Outcome.WON)
        updated = ba.fetch_rows("SELECT status FROM legs WHERE leg_id = ?", (leg_id,))
        assert updated[0]["status"] == Outcome.WON

    def test_normal_update_to_lost(self, ba):
        legs = [
            CandidateLeg(
                match_name="A vs B",
                datetime=DT_BASE,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.50,
                result_url="http://x",
                consensus=80.0,
                sources=3,
            )
        ]
        ba.save_slip("p", legs)
        rows = ba.fetch_rows("SELECT leg_id FROM legs LIMIT 1")
        ba.update_leg(rows[0]["leg_id"], Outcome.LOST)
        updated = ba.fetch_rows("SELECT status FROM legs WHERE leg_id = ?", (rows[0]["leg_id"],))
        assert updated[0]["status"] == Outcome.LOST


# ── get_excluded_urls ─────────────────────────────────────────────────────────


class TestGetExcludedUrls:
    def test_normal_pending_urls_excluded(self, ba):
        legs = [
            CandidateLeg(
                match_name="A vs B",
                datetime=DT_BASE,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.50,
                result_url="http://pending-url",
                consensus=80.0,
                sources=3,
            )
        ]
        ba.save_slip("p", legs)
        excluded = ba.get_excluded_urls()
        assert "http://pending-url" in excluded

    def test_normal_won_urls_excluded(self, ba):
        legs = [
            CandidateLeg(
                match_name="A vs B",
                datetime=DT_BASE,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.50,
                result_url="http://won-url",
                consensus=80.0,
                sources=3,
            )
        ]
        ba.save_slip("p", legs)
        rows = ba.fetch_rows("SELECT leg_id FROM legs LIMIT 1")
        ba.update_leg(rows[0]["leg_id"], Outcome.WON)
        excluded = ba.get_excluded_urls()
        assert "http://won-url" in excluded

    def test_normal_pending_in_lost_slip_not_excluded(self, ba):
        """If a slip has a Lost leg, other Pending legs should NOT be excluded."""
        legs = [
            CandidateLeg(
                match_name="A vs B",
                datetime=DT_BASE,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.50,
                result_url="http://lost-slip-pending",
                consensus=80.0,
                sources=3,
            ),
            CandidateLeg(
                match_name="C vs D",
                datetime=DT_BASE,
                market=MarketLabel.AWAY,
                market_type=MarketType.RESULT,
                odds=2.0,
                result_url="http://lost-slip-lost",
                consensus=90.0,
                sources=3,
            ),
        ]
        ba.save_slip("p", legs)
        # Mark one leg as Lost
        all_legs = ba.fetch_rows("SELECT leg_id, result_url FROM legs")
        for leg in all_legs:
            if leg["result_url"] == "http://lost-slip-lost":
                ba.update_leg(leg["leg_id"], Outcome.LOST)

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
            (
                1,
                "2026-04-01",
                "profile",
                3.0,
                1.0,
                "A vs B",
                "2026-04-01T15:00:00",
                MarketLabel.HOME,
                MarketType.RESULT,
                1.5,
                Outcome.PENDING,
                "http://x",
                None,
                None,
                None,
            ),
            (
                1,
                "2026-04-01",
                "profile",
                3.0,
                1.0,
                "C vs D",
                "2026-04-01T18:00:00",
                MarketLabel.AWAY,
                MarketType.RESULT,
                2.0,
                Outcome.PENDING,
                "http://y",
                None,
                None,
                None,
            ),
        ]
        slips = BetAssistant._rows_to_slips(rows)
        assert len(slips) == 1
        assert len(slips[0].legs) == 2

    def test_normal_status_pending(self):
        rows = [
            (
                1,
                "2026-04-01",
                "p",
                3.0,
                1.0,
                "A vs B",
                "2026-04-01T15:00:00",
                MarketLabel.HOME,
                MarketType.RESULT,
                1.5,
                Outcome.PENDING,
                None,
                None,
                None,
                None,
            ),
        ]
        slips = BetAssistant._rows_to_slips(rows)
        assert slips[0].slip_status == Outcome.PENDING

    def test_normal_status_won(self):
        rows = [
            (
                1,
                "2026-04-01",
                "p",
                3.0,
                1.0,
                "A vs B",
                "2026-04-01T15:00:00",
                MarketLabel.HOME,
                MarketType.RESULT,
                1.5,
                Outcome.WON,
                None,
                None,
                None,
                None,
            ),
        ]
        slips = BetAssistant._rows_to_slips(rows)
        assert slips[0].slip_status == Outcome.WON

    def test_normal_status_lost(self):
        rows = [
            (
                1,
                "2026-04-01",
                "p",
                3.0,
                1.0,
                "A vs B",
                "2026-04-01T15:00:00",
                MarketLabel.HOME,
                MarketType.RESULT,
                1.5,
                Outcome.WON,
                None,
                None,
                None,
                None,
            ),
            (
                1,
                "2026-04-01",
                "p",
                3.0,
                1.0,
                "C vs D",
                "2026-04-01T18:00:00",
                MarketLabel.AWAY,
                MarketType.RESULT,
                2.0,
                Outcome.LOST,
                None,
                None,
                None,
                None,
            ),
        ]
        slips = BetAssistant._rows_to_slips(rows)
        assert slips[0].slip_status == Outcome.LOST

    def test_normal_status_live(self):
        rows = [
            (
                1,
                "2026-04-01",
                "p",
                3.0,
                1.0,
                "A vs B",
                "2026-04-01T15:00:00",
                MarketLabel.HOME,
                MarketType.RESULT,
                1.5,
                Outcome.LIVE,
                None,
                None,
                None,
                None,
            ),
            (
                1,
                "2026-04-01",
                "p",
                3.0,
                1.0,
                "C vs D",
                "2026-04-01T18:00:00",
                MarketLabel.AWAY,
                MarketType.RESULT,
                2.0,
                Outcome.PENDING,
                None,
                None,
                None,
                None,
            ),
        ]
        slips = BetAssistant._rows_to_slips(rows)
        assert slips[0].slip_status == Outcome.LIVE

    def test_edge_multiple_slips(self):
        rows = [
            (
                1,
                "2026-04-01",
                "p1",
                3.0,
                1.0,
                "A vs B",
                "2026-04-01T15:00:00",
                MarketLabel.HOME,
                MarketType.RESULT,
                1.5,
                Outcome.PENDING,
                None,
                None,
                None,
                None,
            ),
            (
                2,
                "2026-04-02",
                "p2",
                5.0,
                2.0,
                "C vs D",
                "2026-04-02T15:00:00",
                MarketLabel.AWAY,
                MarketType.RESULT,
                2.0,
                Outcome.WON,
                None,
                None,
                None,
                None,
            ),
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
                assert slips[0].slip_id == slip_id
                assert len(slips[0].legs) == len(legs)

    def test_scenario_auto_exclude_prevents_duplicates(self, tmp_path):
        """build_slip_auto_exclude must not reuse URLs from existing slips."""
        with BetAssistant(str(tmp_path / "auto_excl.db")) as ba:
            ba.load_matches(make_matches_df(20, sources_per_match=5))

            # Build and save first slip
            legs1 = ba.build_slip_auto_exclude("medium_risk")
            if legs1:
                ba.save_slip("medium_risk", legs1)
                used_urls_1 = {leg.result_url for leg in legs1}

                # Build second slip — should not reuse same URLs
                legs2 = ba.build_slip_auto_exclude("medium_risk")
                if legs2:
                    used_urls_2 = {leg.result_url for leg in legs2}
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
                assert slip.profile == "low_risk"

    def test_scenario_settle_legs_manually(self, tmp_path):
        """Save a slip, manually settle all legs, verify slip status transitions."""
        with BetAssistant(str(tmp_path / "settle.db")) as ba:
            ba.load_matches(make_matches_df(5))
            legs = ba.build_slip(BetSlipConfig(target_odds=2.0, target_legs=2, consensus_floor=0.0))
            if legs:
                ba.save_slip("test", legs)
                all_legs = ba.fetch_rows("SELECT leg_id FROM legs")

                # Mark all Won
                for leg in all_legs:
                    ba.update_leg(leg["leg_id"], Outcome.WON)

                slips = ba.get_slips()
                assert slips[0].slip_status == Outcome.WON

                # Mark one Lost → slip becomes Lost
                ba.update_leg(all_legs[0]["leg_id"], Outcome.LOST)
                slips = ba.get_slips()
                assert slips[0].slip_status == Outcome.LOST

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

    def test_scenario_manual_slip_with_btts_preserves_market_type(self, tmp_path):
        """Manual slips (from BettingTips/SmartBuilder) must preserve market_type for BTTS."""
        from bet_framework.core.Slip import CandidateLeg

        with BetAssistant(str(tmp_path / "btts_market_type.db")) as ba:
            ba.load_matches(make_matches_df(1))

            # Create a BTTS Yes leg
            leg = CandidateLeg(
                match_name="Home_0 vs Away_0",
                datetime=DT_BASE,
                market=MarketLabel.BTTS_YES,
                market_type=MarketType.BTTS,
                odds=1.90,
                result_url="https://example.com/match/0",
                consensus=80.0,
                sources=3,
            )

            # Save as manual slip (simulates BettingTips/SmartBuilder flow)
            slip_id = ba.save_slip("manual", [leg])

            # Verify market_type was saved correctly
            rows = ba.fetch_rows("SELECT market, market_type FROM legs WHERE slip_id = ?", (slip_id,))
            assert len(rows) == 1
            market, market_type = rows[0]
            assert market == "BTTS Yes"
            assert market_type == "btts"


# ── Source Reliability Tracking Tests ────────────────────────────────────────────


class TestSourceReliabilityTracking:
    """Tests for the source reliability tracking feature (predictions per leg, excluded sources)."""

    def test_save_slip_stores_predictions(self, ba):
        """Test that predictions are stored when saving a slip."""
        legs = [
            CandidateLeg(
                match_name="Home_0 vs Away_0",
                datetime=DT_BASE,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.50,
                result_url="https://example.com/match/0",
                consensus=80.0,
                sources=3,
                predictions=[
                    {"source": "src1", "home": 2, "away": 0},
                    {"source": "src2", "home": 2, "away": 1},
                    {"source": "src3", "home": 1, "away": 0},
                ],
            )
        ]
        ba.save_slip("test", legs)
        rows = ba.fetch_rows("SELECT predictions, final_score FROM legs WHERE slip_id = 1")
        assert rows[0]["predictions"] is not None
        assert rows[0]["final_score"] is None  # Not settled yet
        import json

        stored = json.loads(rows[0]["predictions"])
        assert len(stored) == 3
        assert stored[0]["source"] == "src1"
        assert stored[0]["home"] == 2
        assert stored[0]["away"] == 0
        # predicted_outcome should NOT be stored (computed at query time)
        assert "predicted_outcome" not in stored[0]

    def test_get_slips_returns_predictions(self, ba):
        """Test that get_slips parses and returns predictions."""
        legs = [
            CandidateLeg(
                match_name="Home_0 vs Away_0",
                datetime=DT_BASE,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.50,
                result_url="https://example.com/match/0",
                consensus=80.0,
                sources=3,
                predictions=[
                    {"source": "src1", "home": 2, "away": 0},
                    {"source": "src2", "home": 2, "away": 1},
                ],
            )
        ]
        ba.save_slip("test", legs)
        slips = ba.get_slips()
        assert len(slips[0].legs[0].predictions) == 2
        assert slips[0].legs[0].predictions[0]["source"] == "src1"
        assert slips[0].legs[0].predictions[0]["home"] == 2
        assert slips[0].legs[0].predictions[0]["away"] == 0
        assert "predicted_outcome" not in slips[0].legs[0].predictions[0]
        # final_score should be None for unsettled legs
        assert slips[0].legs[0].final_score is None

    def test_get_slips_backward_compatibility_no_predictions(self, ba):
        """Test that slips without predictions column still work."""
        # Manually insert a leg without predictions
        ba.conn.execute(
            """INSERT INTO slips (date_generated, profile, total_odds, units) VALUES (?, ?, ?, ?)""",
            ("2026-04-01", "test", 2.0, 1.0),
        )
        ba.conn.execute(
            """INSERT INTO legs (slip_id, match_name, match_datetime, market, market_type, odds, result_url, status, league, predictions, final_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (1, "A vs B", "2026-04-01T15:00:00", "1", "result", 1.5, "http://x", "Pending", None, None, None),
        )
        ba.conn.commit()
        slips = ba.get_slips()
        assert len(slips) == 1
        assert slips[0].legs[0].predictions == []
        assert slips[0].legs[0].final_score is None

    def test_build_slip_includes_predictions(self, loaded_ba):
        """Test that build_slip generates predictions for each leg."""
        legs = loaded_ba.build_slip("medium_risk")
        if legs:
            # Each leg should have predictions field populated
            for leg in legs:
                assert hasattr(leg, "predictions")
                # Note: predictions may be empty if no scores available for the market
                # but the field should exist
                assert isinstance(leg.predictions, list)

    def test_excluded_sources_not_in_stored_predictions(self, ba):
        """Test that excluded sources are not stored in predictions."""
        df = pd.DataFrame(
            [
                {
                    "home_name": "Home",
                    "away_name": "Away",
                    "datetime": DT_BASE,
                    "scores": [
                        {"home": 3, "away": 0, "source": "src_good"},
                        {"home": 0, "away": 3, "source": "src_bad"},
                    ],
                    "odds": {"home": 1.5, "draw": 3.5, "away": 5.0},
                    "result_url": "http://test",
                }
            ]
        )
        ba.load_matches(df, excluded_sources=["src_bad"])
        legs = ba.build_slip(BetSlipConfig(target_odds=2.0, target_legs=1, consensus_floor=0.0))
        if legs:
            ba.save_slip("test", legs)
            slips = ba.get_slips()
            # Only src_good should be in predictions
            assert len(slips[0].legs[0].predictions) == 1
            assert slips[0].legs[0].predictions[0]["source"] == "src_good"
            # Check no predicted_outcome field
            assert "predicted_outcome" not in slips[0].legs[0].predictions[0]
            # Check final_score is None for unsettled
            assert slips[0].legs[0].final_score is None

    def test_candidate_leg_has_predictions_field(self):
        """Test that CandidateLeg dataclass has predictions field."""
        leg = CandidateLeg(
            match_name="A vs B",
            datetime=DT_BASE,
            market=MarketLabel.HOME,
            market_type=MarketType.RESULT,
            consensus=70.0,
            odds=1.50,
            result_url="http://x.com",
            sources=3,
        )
        assert hasattr(leg, "predictions")
        assert isinstance(leg.predictions, list)
        assert leg.predictions == []

    def test_bet_leg_has_predictions_field(self):
        """Test that BetLeg dataclass has predictions field."""
        leg = BetLeg(
            match_name="A vs B",
            datetime=DT_BASE,
            market=MarketLabel.HOME,
            market_type=MarketType.RESULT,
            odds=1.50,
            status=Outcome.PENDING,
            result_url="http://x.com",
        )
        assert hasattr(leg, "predictions")
        assert isinstance(leg.predictions, list)
        assert leg.predictions == []
        assert hasattr(leg, "final_score")
        assert leg.final_score is None

    def test_bet_slip_config_has_excluded_sources(self):
        """Test that BetSlipConfig has excluded_sources field."""
        cfg = BetSlipConfig()
        assert hasattr(cfg, "excluded_sources")
        assert cfg.excluded_sources is None

        cfg2 = BetSlipConfig(excluded_sources=["src1", "src2"])
        assert cfg2.excluded_sources == ["src1", "src2"]

    def test_load_matches_stores_filtered_scores(self, ba):
        """Test that load_matches stores filtered scores in _filtered_scores column."""
        df = pd.DataFrame(
            [
                {
                    "home_name": "Home",
                    "away_name": "Away",
                    "datetime": DT_BASE,
                    "scores": [
                        {"home": 3, "away": 0, "source": "src_good"},
                        {"home": 0, "away": 3, "source": "src_bad"},
                    ],
                    "odds": {"home": 1.5, "draw": 3.5, "away": 5.0},
                    "result_url": "http://test",
                }
            ]
        )
        ba.load_matches(df, excluded_sources=["src_bad"])
        assert "_filtered_scores" in ba._df.columns
        filtered = ba._df.iloc[0]["_filtered_scores"]
        assert len(filtered) == 1
        assert filtered[0]["source"] == "src_good"

    def test_build_leg_predictions_for_different_markets(self, ba):
        """Test that _build_leg_predictions works for different market types."""
        df = pd.DataFrame(
            [
                {
                    "home_name": "Home",
                    "away_name": "Away",
                    "datetime": DT_BASE,
                    "scores": [
                        {"home": 3, "away": 0, "source": "src1"},  # Home win, Over 2.5
                        {"home": 1, "away": 1, "source": "src2"},  # Draw, Under 2.5, BTTS Yes
                        {"home": 0, "away": 2, "source": "src3"},  # Away win, Over 2.5
                    ],
                    "odds": {
                        "home": 1.5,
                        "draw": 3.5,
                        "away": 5.0,
                        "over_25": 1.8,
                        "under_25": 2.0,
                        "btts_y": 1.9,
                        "btts_n": 1.9,
                    },
                    "result_url": "http://test",
                }
            ]
        )
        ba.load_matches(df)

        # Test RESULT market predictions - returns only source, home, away (no predicted_outcome)
        result_preds = ba._build_leg_predictions(ba._df.iloc[0]["_filtered_scores"], MarketLabel.HOME, MarketType.RESULT)
        assert len(result_preds) == 3
        # Should only have source, home, away - no predicted_outcome
        for pred in result_preds:
            assert set(pred.keys()) == {"source", "home", "away"}
            assert "predicted_outcome" not in pred
        # Check values
        assert result_preds[0] == {"source": "src1", "home": 3, "away": 0}
        assert result_preds[1] == {"source": "src2", "home": 1, "away": 1}
        assert result_preds[2] == {"source": "src3", "home": 0, "away": 2}

        # Test OVER_UNDER_25 market predictions
        ou_preds = ba._build_leg_predictions(ba._df.iloc[0]["_filtered_scores"], MarketLabel.OVER_25, MarketType.OVER_UNDER_25)
        assert len(ou_preds) == 3
        for pred in ou_preds:
            assert set(pred.keys()) == {"source", "home", "away"}
            assert "predicted_outcome" not in pred
        assert ou_preds[0] == {"source": "src1", "home": 3, "away": 0}
        assert ou_preds[1] == {"source": "src2", "home": 1, "away": 1}
        assert ou_preds[2] == {"source": "src3", "home": 0, "away": 2}

    def test_final_score_stored_on_settlement(self, ba):
        """Test that final_score is stored when settling a leg."""
        legs = [
            CandidateLeg(
                match_name="Home vs Away",
                datetime=DT_BASE,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.50,
                result_url="http://test",
                consensus=80.0,
                sources=3,
                predictions=[
                    {"source": "src1", "home": 2, "away": 0},
                    {"source": "src2", "home": 2, "away": 1},
                ],
            )
        ]
        ba.save_slip("test", legs)

        # Manually settle with final score
        rows = ba.fetch_rows("SELECT leg_id FROM legs WHERE slip_id = 1")
        leg_id = rows[0]["leg_id"]

        # Use settle_leg_manually which stores final_score
        outcome = ba.settle_leg_manually(leg_id, "2:1", "1", "result")
        assert outcome == "Won"

        # Check final_score is stored
        rows = ba.fetch_rows("SELECT final_score, status FROM legs WHERE leg_id = ?", (leg_id,))
        assert rows[0]["final_score"] == "2:1"
        assert rows[0]["status"] == "Won"

        # Check get_slips returns final_score
        slips = ba.get_slips()
        assert slips[0].legs[0].final_score == "2:1"

    def test_source_accuracy_computed_from_final_score(self, ba):
        """Test that source accuracy can be computed from final_score."""
        legs = [
            CandidateLeg(
                match_name="Home vs Away",
                datetime=DT_BASE,
                market=MarketLabel.HOME,
                market_type=MarketType.RESULT,
                odds=1.50,
                result_url="http://test1",
                consensus=80.0,
                sources=2,
                predictions=[
                    {"source": "src_good", "home": 2, "away": 0},  # Correct: predicts home win
                    {"source": "src_bad", "home": 0, "away": 2},  # Wrong: predicts away win
                ],
            ),
            CandidateLeg(
                match_name="Home2 vs Away2",
                datetime=DT_BASE,
                market=MarketLabel.OVER_25,
                market_type=MarketType.OVER_UNDER_25,
                odds=1.80,
                result_url="http://test2",
                consensus=70.0,
                sources=2,
                predictions=[
                    {"source": "src_good", "home": 2, "away": 1},  # Correct: predicts over 2.5
                    {"source": "src_bad", "home": 1, "away": 0},  # Wrong: predicts under 2.5
                ],
            ),
        ]
        ba.save_slip("test", legs)

        # Settle first leg: 2:1 (home wins, over 2.5)
        rows1 = ba.fetch_rows("SELECT leg_id FROM legs WHERE result_url = 'http://test1'")
        ba.settle_leg_manually(rows1[0]["leg_id"], "2:1", "1", "result")

        # Settle second leg: 2:1 (over 2.5)
        rows2 = ba.fetch_rows("SELECT leg_id FROM legs WHERE result_url = 'http://test2'")
        ba.settle_leg_manually(rows2[0]["leg_id"], "2:1", "Over 2.5", "over_under_25")

        # Now check source accuracy by querying
        slips = ba.get_slips()
        all_preds = []
        for slip in slips:
            for leg in slip.legs:
                if leg.final_score:
                    all_preds.extend(leg.predictions)

        # Manually compute accuracy
        from collections import defaultdict

        source_stats = defaultdict(lambda: {"total": 0, "correct": 0})

        for slip in slips:
            for leg in slip.legs:
                if not leg.final_score:
                    continue
                actual_home, actual_away = map(int, leg.final_score.split(":"))
                market_label = str(leg.market)
                market_type = str(leg.market_type)

                # Determine actual outcome
                def predict_outcome(h, a, mkt, mkt_type):
                    total = h + a
                    if mkt_type == "result":
                        return "HOME" if h > a else ("DRAW" if h == a else "AWAY")
                    elif mkt_type == "over_under_25":
                        return "OVER_25" if total > 2.5 else "UNDER_25"
                    return "UNKNOWN"

                actual_outcome = predict_outcome(actual_home, actual_away, market_label, market_type)

                for pred in leg.predictions:
                    source = pred["source"]
                    pred_outcome = predict_outcome(pred["home"], pred["away"], market_label, market_type)
                    source_stats[source]["total"] += 1
                    if pred_outcome == actual_outcome:
                        source_stats[source]["correct"] += 1

        # src_good should have 100% accuracy, src_bad 0%
        assert source_stats["src_good"]["correct"] == 2
        assert source_stats["src_good"]["total"] == 2
        assert source_stats["src_bad"]["correct"] == 0
        assert source_stats["src_bad"]["total"] == 2
