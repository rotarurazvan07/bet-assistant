"""
Gap tests for bet_framework/core/scoring.py (GitHub issue #70).

Covered public API:
  resolve_shrinkage_k / resolve_max_single_leg_odds / resolve_min_pick_quality /
  resolve_min_source_edge      - auto-defaults vs explicit config values
  adjusted_consensus           - Bayesian shrinkage formula spot checks
  classify_odds_movement       - case-insensitive and whitespace variants
  apply_odds_movement_adjustment - stable-direction early return (source line 151)
  score_consensus              - below-floor clamp, monotonicity property
  score_sources                - negative pool maximum, range property
  score_balance                - asymmetric tol_lower/tol_upper, linear vs gaussian
  score_pick                   - tier assignment, max-odds hard gate (line 216),
                                 preadjusted consensus path, tolerance excess
                                 penalty, odds-movement composition

Property-based tests (hypothesis): consensus monotonicity, source score range,
gaussian >= linear decay bound.
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from bet_framework.core.scoring import (
    adjusted_consensus,
    apply_odds_movement_adjustment,
    classify_odds_movement,
    odds_movement_factor,
    resolve_max_single_leg_odds,
    resolve_min_pick_quality,
    resolve_min_source_edge,
    resolve_shrinkage_k,
    resolve_tolerance,
    score_balance,
    score_consensus,
    score_pick,
    score_sources,
)
from bet_framework.core.Slip import BetSlipConfig, CandidateLeg
from bet_framework.core.type_defs import MarketLabel, MarketType

# -- Helpers -------------------------------------------------------------------

DT_BASE_ISO = "2026-04-05T15:00:00"


def make_cfg(**overrides) -> BetSlipConfig:
    """Factory with overrides, mirroring the data-factories pattern."""
    return BetSlipConfig(**overrides)


def make_leg(consensus=80.0, odds=1.5, sources=4, **overrides) -> CandidateLeg:
    """CandidateLeg factory: defaults sit inside every scoring band."""
    kwargs = {
        "match_name": "Team A vs Team B",
        "datetime": DT_BASE_ISO,
        "market": MarketLabel.HOME,
        "market_type": MarketType.RESULT,
        "consensus": consensus,
        "odds": odds,
        "result_url": "https://example.com/match/1",
        "sources": sources,
    }
    kwargs.update(overrides)
    return CandidateLeg(**kwargs)


def quality_only_cfg() -> BetSlipConfig:
    """quality_vs_balance=1.0 -> base score is odds-independent (penalty isolation)."""
    return make_cfg(quality_vs_balance=1.0)


# -- Config resolvers ------------------------------------------------------------


class TestResolveHelpers:
    def test_shrinkage_k_none_defaults_to_three(self):
        assert resolve_shrinkage_k(make_cfg()) == 3.0

    def test_shrinkage_k_explicit_passthrough(self):
        assert resolve_shrinkage_k(make_cfg(consensus_shrinkage_k=7.5)) == 7.5

    def test_shrinkage_k_clamped_low_by_dataclass(self):
        # BetSlipConfig clamps shrinkage_k to [1.0, 10.0] in __post_init__.
        assert resolve_shrinkage_k(make_cfg(consensus_shrinkage_k=0.2)) == 1.0

    def test_max_single_leg_odds_none_defaults_to_35(self):
        assert resolve_max_single_leg_odds(make_cfg()) == 3.5

    def test_max_single_leg_odds_explicit(self):
        assert resolve_max_single_leg_odds(make_cfg(max_single_leg_odds=2.0)) == 2.0

    def test_min_pick_quality_none_defaults(self):
        assert resolve_min_pick_quality(make_cfg()) == 0.20

    def test_min_pick_quality_explicit(self):
        assert resolve_min_pick_quality(make_cfg(min_pick_quality=0.45)) == 0.45

    def test_min_source_edge_none_defaults_to_zero(self):
        assert resolve_min_source_edge(make_cfg()) == 0.0

    def test_min_source_edge_explicit(self):
        assert resolve_min_source_edge(make_cfg(min_source_edge=0.12)) == 0.12


# -- adjusted_consensus (shrinkage formula lives here) -----------------------------


class TestAdjustedConsensusFormula:
    def test_formula_matches_spec(self):
        # adjusted = 50 + (sources / (sources + k)) * (raw - 50)
        assert adjusted_consensus(90.0, 3, 3.0) == pytest.approx(50.0 + (3 / 6) * 40.0)

    def test_default_k_is_three(self):
        assert adjusted_consensus(90.0, 3) == adjusted_consensus(90.0, 3, 3.0)

    def test_resolve_shrinkage_k_feeds_formula(self):
        # [P0] resolve_shrinkage_k flows into the consensus component of quality.
        cfg = make_cfg(
            quality_vs_balance=1.0,
            consensus_vs_sources=1.0,
            consensus_shrinkage_k=9.0,
        )
        leg = make_leg(consensus=80.0, odds=1.5, sources=2)
        _, _score, quality = score_pick(leg, 1.5, 10, cfg)
        shrunk = adjusted_consensus(80.0, 2, 9.0)  # 50 + (2/11)*30
        expected = (shrunk - cfg.consensus_floor) / (100.0 - cfg.consensus_floor)
        assert quality == pytest.approx(expected, abs=1e-6)

    def test_shrinkage_k_changes_score_pick_output(self):
        # Larger k pulls consensus toward 50, lowering the quality component.
        leg = make_leg(consensus=90.0, odds=1.5, sources=2)
        cfg_low_k = make_cfg(
            quality_vs_balance=1.0, consensus_vs_sources=1.0, consensus_shrinkage_k=1.0
        )
        cfg_high_k = make_cfg(
            quality_vs_balance=1.0, consensus_vs_sources=1.0, consensus_shrinkage_k=10.0
        )
        quality_low_k = score_pick(leg, 1.5, 10, cfg_low_k)[2]
        quality_high_k = score_pick(leg, 1.5, 10, cfg_high_k)[2]
        assert quality_low_k > quality_high_k


# -- classify_odds_movement -------------------------------------------------------


class TestClassifyOddsMovement:
    def test_case_insensitive_directions(self):
        assert classify_odds_movement("DOWN") == "confirm"
        assert classify_odds_movement("Up") == "infirm"

    def test_surrounding_whitespace_stripped(self):
        assert classify_odds_movement("  down  ") == "confirm"
        assert classify_odds_movement(" up ") == "infirm"

    def test_unknown_direction_falls_back_to_stable(self):
        assert classify_odds_movement("sideways") == "stable"
        assert classify_odds_movement("") == "stable"

    def test_factor_values(self):
        assert odds_movement_factor("confirm") == 1.0
        assert odds_movement_factor("infirm") == 0.0
        assert odds_movement_factor("stable") == 0.5


# -- apply_odds_movement_adjustment (covers source line 151) -----------------------


class TestApplyOddsMovementAdjustment:
    def test_stable_direction_returns_base_unchanged(self):
        # [P0] Line 151: direction classifies as stable with sufficient
        # strength -> early return, no blending.
        cfg = make_cfg(odds_movement_weight=0.30, odds_movement_strength_min=0.05)
        assert apply_odds_movement_adjustment(0.8, "stable", 0.10, cfg) == 0.8

    def test_unknown_direction_string_is_stable(self):
        cfg = make_cfg(odds_movement_weight=0.30, odds_movement_strength_min=0.05)
        assert apply_odds_movement_adjustment(0.8, "drifted", 0.50, cfg) == 0.8

    def test_confirm_blends_toward_one(self):
        cfg = make_cfg(odds_movement_weight=0.20)
        result = apply_odds_movement_adjustment(0.5, "down", 0.10, cfg)
        assert result == pytest.approx(0.5 * 0.8 + 0.2 * 1.0)

    def test_infirm_blends_toward_zero(self):
        cfg = make_cfg(odds_movement_weight=0.20)
        result = apply_odds_movement_adjustment(0.5, "up", 0.10, cfg)
        assert result == pytest.approx(0.5 * 0.8 + 0.2 * 0.0)

    def test_weight_capped_at_thirty_percent(self):
        # resolve_odds_movement_weight caps at 0.30 even if dataclass allowed more.
        cfg = make_cfg(odds_movement_weight=0.30)
        result = apply_odds_movement_adjustment(0.5, "down", 0.10, cfg)
        assert result == pytest.approx(0.5 * 0.7 + 0.3 * 1.0)


# -- score_consensus ---------------------------------------------------------------


class TestScoreConsensusEdges:
    def test_below_floor_clamps_to_zero(self):
        cfg = make_cfg(consensus_floor=60.0)
        assert score_consensus(45.0, cfg) == 0.0

    def test_above_hundred_clamps_to_one(self):
        cfg = make_cfg(consensus_floor=50.0)
        assert score_consensus(120.0, cfg) == 1.0

    def test_floor_equal_to_hundred_spans_zero(self):
        # span <= 0 -> always 1.0
        cfg = make_cfg(consensus_floor=100.0)
        assert score_consensus(0.0, cfg) == 1.0
        assert score_consensus(100.0, cfg) == 1.0

    @settings(deadline=None)
    @given(
        c1=st.floats(min_value=0.0, max_value=100.0),
        c2=st.floats(min_value=0.0, max_value=100.0),
        floor=st.floats(min_value=0.0, max_value=100.0),
    )
    def test_property_monotonic_non_decreasing_in_consensus(self, c1, c2, floor):
        cfg = make_cfg(consensus_floor=floor)
        lo, hi = sorted((c1, c2))
        assert score_consensus(lo, cfg) <= score_consensus(hi, cfg) + 1e-9


# -- score_sources -----------------------------------------------------------------


class TestScoreSourcesEdges:
    def test_negative_max_sources_returns_zero(self):
        assert score_sources(3, -1) == 0.0

    def test_sources_exceeding_max_clamps_to_one(self):
        assert score_sources(12, 10) == 1.0

    def test_zero_sources_returns_zero(self):
        assert score_sources(0, 10) == 0.0

    @settings(deadline=None)
    @given(
        sources=st.integers(min_value=0, max_value=100),
        max_sources=st.integers(min_value=-5, max_value=100),
    )
    def test_property_score_in_unit_range(self, sources, max_sources):
        assert 0.0 <= score_sources(sources, max_sources) <= 1.0


# -- score_balance -----------------------------------------------------------------


class TestScoreBalanceToleranceBands:
    def test_explicit_lower_band_overrides_default(self):
        cfg = make_cfg(tol_lower=0.40, balance_decay="linear")
        # odds below ideal: uses tol_lower=0.40 (deviation 0.2 -> score 0.5)
        assert score_balance(1.20, 1.50, 0.20, cfg) == pytest.approx(0.5)

    def test_explicit_upper_band_overrides_default(self):
        cfg = make_cfg(tol_upper=0.40, balance_decay="linear")
        # odds above ideal: uses tol_upper=0.40 (deviation 0.2 -> score 0.5).
        # Default would be 0.6 * tolerance = 0.12 -> 0.0.
        assert score_balance(1.80, 1.50, 0.20, cfg) == pytest.approx(0.5)

    def test_default_upper_band_is_sixty_percent_of_tolerance(self):
        cfg = make_cfg(balance_decay="linear")
        # dev = 0.15/1.5 = 0.10; upper tol = 0.20*0.6 = 0.12 -> score = 1 - 10/12
        assert score_balance(1.65, 1.50, 0.20, cfg) == pytest.approx(1.0 - 0.10 / 0.12)

    def test_linear_decays_to_zero_beyond_band(self):
        cfg = make_cfg(balance_decay="linear")
        assert score_balance(2.50, 1.50, 0.20, cfg) == 0.0

    def test_gaussian_stays_positive_far_from_ideal(self):
        cfg = make_cfg(balance_decay="gaussian")
        # dev = 1.0/1.5 = 0.667, upper tol = 0.12 -> exp(-0.5*(5.56)^2) ~ 2e-7
        assert score_balance(2.50, 1.50, 0.20, cfg) > 0.0

    def test_gaussian_at_ideal_is_one(self):
        cfg = make_cfg(balance_decay="gaussian")
        assert score_balance(1.50, 1.50, 0.20, cfg) == 1.0

    @settings(deadline=None)
    @given(
        odds=st.floats(min_value=1.0, max_value=3.0),
        ideal=st.floats(min_value=1.0, max_value=3.0),
        tol=st.floats(min_value=0.05, max_value=0.80),
    )
    def test_property_gaussian_never_below_linear(self, odds, ideal, tol):
        # With explicit symmetric bands both decay paths get the same tol.
        linear_cfg = make_cfg(tol_lower=tol, tol_upper=tol, balance_decay="linear")
        gauss_cfg = make_cfg(tol_lower=tol, tol_upper=tol, balance_decay="gaussian")
        linear_score = score_balance(odds, ideal, tol, linear_cfg)
        gauss_score = score_balance(odds, ideal, tol, gauss_cfg)
        assert gauss_score >= linear_score - 1e-9


# -- score_pick ----------------------------------------------------------------------


class TestScorePickTiers:
    def test_at_ideal_odds_is_tier_one(self):
        tier, score, quality = score_pick(make_leg(odds=1.5), 1.5, 10, make_cfg())
        assert tier == 1
        assert 0.0 < score <= 1.0
        assert 0.0 < quality <= 1.0

    def test_just_inside_upper_band_is_tier_one(self):
        # dev = 0.14/1.5 = 0.0933 <= auto upper tol 0.0975
        tier, _, _ = score_pick(make_leg(odds=1.64), 1.5, 10, make_cfg())
        assert tier == 1

    def test_just_outside_upper_band_is_tier_two(self):
        # dev = 0.15/1.5 = 0.10 > auto upper tol 0.0975
        tier, _, _ = score_pick(make_leg(odds=1.65), 1.5, 10, make_cfg())
        assert tier == 2

    def test_just_inside_lower_band_is_tier_one(self):
        # dev = -0.24/1.5 = -0.16 <= tolerance 0.1625
        tier, _, _ = score_pick(make_leg(odds=1.26), 1.5, 10, make_cfg())
        assert tier == 1

    def test_just_outside_lower_band_is_tier_two(self):
        # dev = -0.30/1.5 = -0.20 > tolerance 0.1625
        tier, _, _ = score_pick(make_leg(odds=1.20), 1.5, 10, make_cfg())
        assert tier == 2

    def test_symmetric_explicit_bands(self):
        cfg = make_cfg(tol_lower=0.30, tol_upper=0.30)
        # dev = +/-0.25: inside both bands
        assert score_pick(make_leg(odds=1.875), 1.5, 10, cfg)[0] == 1
        assert score_pick(make_leg(odds=1.125), 1.5, 10, cfg)[0] == 1


class TestScorePickMaxOddsGate:
    def test_odds_above_default_gate_returns_tier_two_zeros(self):
        # [P0] Line 216: hard gate at resolve_max_single_leg_odds() default 3.5.
        leg = make_leg(odds=3.6)
        assert score_pick(leg, 1.5, 10, make_cfg()) == (2, 0.0, 0.0)

    def test_odds_equal_to_gate_passes_through(self):
        leg = make_leg(odds=3.5)
        tier, score, _ = score_pick(leg, 3.5, 10, make_cfg())
        assert (tier, score) != (2, 0.0)

    def test_explicit_lower_gate(self):
        cfg = make_cfg(max_single_leg_odds=2.0)
        leg = make_leg(odds=2.5)
        assert score_pick(leg, 1.5, 10, cfg) == (2, 0.0, 0.0)

    def test_gate_fires_before_any_tier_logic(self):
        # Even a perfect-balance pick above the gate returns zeros.
        cfg = make_cfg(max_single_leg_odds=2.0)
        leg = make_leg(odds=2.5)
        assert score_pick(leg, 2.5, 10, cfg) == (2, 0.0, 0.0)


class TestScorePickPreadjusted:
    def test_preadjusted_consensus_used_when_flag_set(self):
        # Same _adjusted_consensus, different raw consensus -> identical output.
        leg_a = make_leg(consensus=60.0, _adjusted_consensus=90.0)
        leg_b = make_leg(consensus=99.0, _adjusted_consensus=90.0)
        result_a = score_pick(leg_a, 1.5, 10, make_cfg(), use_preadjusted=True)
        result_b = score_pick(leg_b, 1.5, 10, make_cfg(), use_preadjusted=True)
        assert result_a == result_b

    def test_flag_disabled_ignores_preadjusted_value(self):
        leg_a = make_leg(consensus=60.0, _adjusted_consensus=90.0)
        leg_b = make_leg(consensus=99.0, _adjusted_consensus=90.0)
        result_a = score_pick(leg_a, 1.5, 10, make_cfg(), use_preadjusted=False)
        result_b = score_pick(leg_b, 1.5, 10, make_cfg(), use_preadjusted=False)
        assert result_a != result_b

    def test_zero_preadjusted_falls_back_to_shrinkage(self):
        # _adjusted_consensus <= 0 -> compute from raw consensus.
        leg_zero = make_leg(consensus=80.0, _adjusted_consensus=0.0)
        leg_plain = make_leg(consensus=80.0)
        assert score_pick(
            leg_zero, 1.5, 10, make_cfg(), use_preadjusted=True
        ) == score_pick(leg_plain, 1.5, 10, make_cfg(), use_preadjusted=True)


class TestScorePickExcessPenalty:
    def test_out_of_tolerance_pick_scored_below_quality(self):
        # With quality_vs_balance=1.0, base == quality; tier-2 penalty applies.
        cfg = quality_only_cfg()
        leg = make_leg(odds=1.5)
        _, in_score, quality = score_pick(leg, 1.5, 10, cfg)
        assert in_score == pytest.approx(quality, abs=1e-6)  # no penalty inside band
        _, out_score, _ = score_pick(make_leg(odds=1.65), 1.5, 10, cfg)
        assert out_score < quality  # exp(-8 * 0.0025) penalty applied

    def test_penalty_grows_with_distance_from_band(self):
        cfg = quality_only_cfg()
        near = score_pick(make_leg(odds=1.66), 1.5, 10, cfg)[1]  # dev 0.107
        far = score_pick(make_leg(odds=2.00), 1.5, 10, cfg)[1]  # dev 0.333
        assert 0.0 < far < near

    def test_penalty_formula_matches_lambda_eight(self):
        cfg = quality_only_cfg()
        leg = make_leg(odds=1.65)  # excess = 0.10 - 0.0975 = 0.0025
        _, score, quality = score_pick(leg, 1.5, 10, cfg)
        expected = quality * math.exp(-8.0 * 0.0025)
        assert score == pytest.approx(expected, abs=1e-6)


class TestScorePickMovementIntegration:
    def test_confirm_movement_raises_final_score(self):
        cfg = make_cfg()
        plain = make_leg(odds=1.5)
        moved = make_leg(
            odds=1.5, odds_movement_direction="down", odds_movement_strength=0.10
        )
        plain_result = score_pick(plain, 1.5, 10, cfg)
        moved_result = score_pick(moved, 1.5, 10, cfg)
        assert moved_result[1] > plain_result[1]
        assert moved_result[0] == plain_result[0]  # tier unaffected
        assert moved_result[2] == plain_result[2]  # quality unaffected

    def test_infirm_movement_lowers_final_score(self):
        cfg = make_cfg()
        plain = make_leg(odds=1.5)
        moved = make_leg(
            odds=1.5, odds_movement_direction="up", odds_movement_strength=0.10
        )
        assert score_pick(moved, 1.5, 10, cfg)[1] < score_pick(plain, 1.5, 10, cfg)[1]

    def test_weak_movement_is_ignored(self):
        cfg = make_cfg()  # strength_min auto = 0.05
        plain = make_leg(odds=1.5)
        weak = make_leg(
            odds=1.5, odds_movement_direction="down", odds_movement_strength=0.01
        )
        assert score_pick(weak, 1.5, 10, cfg)[1] == score_pick(plain, 1.5, 10, cfg)[1]

    def test_scores_rounded_to_six_decimals(self):
        _, score, quality = score_pick(make_leg(odds=1.62), 1.5, 10, make_cfg())
        assert score == round(score, 6)
        assert quality == round(quality, 6)


class TestScorePickWeights:
    def test_quality_only_config_ignores_balance(self):
        # Two picks with identical quality inputs but different balance
        # must score identically when quality_vs_balance == 1.0.
        cfg = make_cfg(quality_vs_balance=1.0)
        balanced = make_leg(odds=1.5)
        drifted = make_leg(odds=1.30)  # still within lower band -> tier 1
        assert score_pick(balanced, 1.5, 10, cfg)[1] == pytest.approx(
            score_pick(drifted, 1.5, 10, cfg)[1], abs=1e-6
        )

    def test_balance_only_config_ignores_quality(self):
        cfg = make_cfg(quality_vs_balance=0.0)
        strong = make_leg(consensus=95.0, sources=10)
        weak = make_leg(consensus=51.0, sources=1)
        assert score_pick(strong, 1.5, 10, cfg)[1] == pytest.approx(
            score_pick(weak, 1.5, 10, cfg)[1], abs=1e-6
        )

    def test_consensus_vs_sources_blend(self):
        # [P0] consensus_vs_sources=1.0 -> quality is pure consensus component.
        # Use the preadjusted path so the un-shrunk consensus=100 is scored.
        cfg = make_cfg(quality_vs_balance=1.0, consensus_vs_sources=1.0)
        leg = make_leg(consensus=100.0, sources=1, _adjusted_consensus=100.0)
        _, score, quality = score_pick(leg, 1.5, 10, cfg, use_preadjusted=True)
        assert quality == pytest.approx(1.0, abs=1e-6)
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_preadjusted_score_component_matches_manual_computation(self):
        # Manual recompute of the whole pipeline with preadjusted consensus.
        cfg = make_cfg(quality_vs_balance=1.0, consensus_vs_sources=1.0)
        leg = make_leg(consensus=100.0, sources=1, _adjusted_consensus=100.0)
        _, score, quality = score_pick(leg, 1.5, 10, cfg, use_preadjusted=True)
        c = (100.0 - cfg.consensus_floor) / (100.0 - cfg.consensus_floor)
        assert quality == pytest.approx(c, abs=1e-6)

    def test_tolerance_resolver_used_by_score_pick(self):
        # Explicit tolerance_factor flows through tier assignment.
        cfg = make_cfg(tolerance_factor=0.05, tol_lower=0.05, tol_upper=0.05)
        inside = make_leg(odds=1.57)  # dev = 0.0467 <= 0.05
        outside = make_leg(odds=1.60)  # dev = 0.0667 > 0.05
        assert score_pick(inside, 1.5, 10, cfg)[0] == 1
        assert score_pick(outside, 1.5, 10, cfg)[0] == 2
        assert resolve_tolerance(cfg) == 0.05
