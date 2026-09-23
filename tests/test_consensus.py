"""
Gap tests for bet_framework/core/consensus.py (GitHub issue #70).

Covered public API:
  to_pct(n, total)          - count->percentage, zero-total guard, 1 d.p. rounding
  calc_consensus(scores)    - empty input, single source, all-draw, mixed split,
                              boundary totals for every over/under line,
                              double-chance tallies, missing / None score keys,
                              mid-iteration exception path (source lines 124-126)
  adjusted_consensus(...)   - the Bayesian shrinkage formula
                              adjusted = 50 + (sources / (sources + k)) * (raw - 50)

Architectural note (documented decision): the shrinkage formula lives in
bet_framework/core/scoring.py::adjusted_consensus, NOT in consensus.py -
calc_consensus only aggregates raw percentages.  Issue #70's description
conflates the two; these tests target the real code locations.

Property-based tests (hypothesis): percentage sums, over/under complements,
BTTS complement, value ranges, single-source degeneracy, double-chance
pairwise coverage, shrinkage bounds and monotonicity.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from bet_framework.core.consensus import calc_consensus, to_pct
from bet_framework.core.scoring import adjusted_consensus

# -- Helpers -----------------------------------------------------------------

MARKET_KEYS = {
    "result",
    "over_under_25",
    "over_under_15",
    "over_under_05",
    "over_under_35",
    "over_under_45",
    "btts",
    "double_chance",
}

OVER_UNDER_MARKETS = (
    "over_under_05",
    "over_under_15",
    "over_under_25",
    "over_under_35",
    "over_under_45",
)

SCORE_DICTS = st.fixed_dictionaries(
    {
        "home": st.integers(min_value=0, max_value=9),
        "away": st.integers(min_value=0, max_value=9),
    }
)
SCORE_LISTS = st.lists(SCORE_DICTS, min_size=1, max_size=15)
SINGLE_SCORE = st.lists(SCORE_DICTS, min_size=1, max_size=1)


def empty_consensus() -> dict:
    """Exact all-zero structure returned for empty or failed input."""
    return {
        "result": {"home": 0.0, "draw": 0.0, "away": 0.0},
        "over_under_25": {"over": 0.0, "under": 0.0},
        "over_under_15": {"over": 0.0, "under": 0.0},
        "over_under_05": {"over": 0.0, "under": 0.0},
        "over_under_35": {"over": 0.0, "under": 0.0},
        "over_under_45": {"over": 0.0, "under": 0.0},
        "btts": {"yes": 0.0, "no": 0.0},
        "double_chance": {"1x": 0.0, "12": 0.0, "x2": 0.0},
    }


def flat_values(result: dict) -> list:
    return [value for market in result.values() for value in market.values()]


# -- to_pct ----------------------------------------------------------------------


class TestToPct:
    def test_normal_counts(self):
        assert to_pct(2, 4) == 50.0
        assert to_pct(1, 4) == 25.0
        assert to_pct(3, 3) == 100.0

    def test_zero_numerator(self):
        assert to_pct(0, 5) == 0.0

    def test_zero_total_returns_zero(self):
        assert to_pct(0, 0) == 0.0
        assert to_pct(7, 0) == 0.0

    def test_rounding_to_one_decimal(self):
        assert to_pct(1, 3) == 33.3
        assert to_pct(2, 3) == 66.7


# -- calc_consensus: structure ----------------------------------------------------


class TestCalcConsensusStructure:
    def test_empty_input_returns_all_zero_structure(self):
        assert calc_consensus([]) == empty_consensus()

    def test_populated_result_has_complete_market_key_set(self):
        result = calc_consensus([{"home": 2, "away": 1}])
        assert set(result.keys()) == MARKET_KEYS

    def test_empty_result_has_complete_market_key_set(self):
        assert set(calc_consensus([]).keys()) == MARKET_KEYS


# -- calc_consensus: aggregation -------------------------------------------------


class TestCalcConsensusAggregation:
    def test_single_source_home_win(self):
        result = calc_consensus([{"home": 2, "away": 1}])
        assert result["result"]["home"] == 100.0
        assert result["result"]["draw"] == 0.0
        assert result["result"]["away"] == 0.0
        assert result["over_under_25"]["over"] == 100.0  # total 3 > 2.5
        assert result["over_under_35"]["under"] == 100.0  # total 3 < 3.5
        assert result["btts"]["yes"] == 100.0
        assert result["double_chance"]["1x"] == 100.0
        assert result["double_chance"]["12"] == 100.0
        assert result["double_chance"]["x2"] == 0.0

    def test_single_source_away_win(self):
        result = calc_consensus([{"home": 0, "away": 3}])
        assert result["result"]["away"] == 100.0
        assert result["over_under_25"]["over"] == 100.0
        assert result["btts"]["no"] == 100.0
        assert result["double_chance"]["1x"] == 0.0
        assert result["double_chance"]["12"] == 100.0
        assert result["double_chance"]["x2"] == 100.0

    def test_all_draw_scores(self):
        result = calc_consensus([{"home": 1, "away": 1}, {"home": 0, "away": 0}])
        assert result["result"]["draw"] == 100.0
        assert result["over_under_25"]["under"] == 100.0  # totals 2 and 0
        assert result["over_under_15"]["over"] == 50.0  # 1+1=2 over, 0+0 under
        assert result["btts"]["yes"] == 50.0
        assert result["btts"]["no"] == 50.0
        assert result["double_chance"]["1x"] == 100.0
        assert result["double_chance"]["12"] == 0.0
        assert result["double_chance"]["x2"] == 100.0

    def test_mixed_three_way_split(self):
        scores = [
            {"home": 2, "away": 0},
            {"home": 1, "away": 1},
            {"home": 0, "away": 2},
        ]
        result = calc_consensus(scores)
        third = pytest.approx(100.0 / 3, abs=0.05)
        assert result["result"]["home"] == third
        assert result["result"]["draw"] == third
        assert result["result"]["away"] == third
        # All totals are exactly 2: under 2.5, over 1.5
        assert result["over_under_25"]["under"] == 100.0
        assert result["over_under_15"]["over"] == 100.0
        # BTTS: only 1:1 qualifies
        assert result["btts"]["yes"] == third
        assert result["btts"]["no"] == pytest.approx(200.0 / 3, abs=0.05)
        # Double chance: two of three scores satisfy each pairwise label
        assert result["double_chance"]["1x"] == pytest.approx(200.0 / 3, abs=0.05)
        assert result["double_chance"]["12"] == pytest.approx(200.0 / 3, abs=0.05)
        assert result["double_chance"]["x2"] == pytest.approx(200.0 / 3, abs=0.05)

    def test_boundary_total_two_goals(self):
        result = calc_consensus([{"home": 2, "away": 0}])
        assert result["over_under_25"]["under"] == 100.0  # 2 <= 2.5
        assert result["over_under_15"]["over"] == 100.0  # 2 > 1.5
        assert result["over_under_05"]["over"] == 100.0

    def test_boundary_total_three_goals(self):
        result = calc_consensus([{"home": 3, "away": 0}])
        assert result["over_under_25"]["over"] == 100.0  # 3 > 2.5
        assert result["over_under_35"]["under"] == 100.0  # 3 < 3.5

    def test_boundary_total_four_goals(self):
        result = calc_consensus([{"home": 3, "away": 1}])
        assert result["over_under_35"]["over"] == 100.0  # 4 > 3.5
        assert result["over_under_45"]["under"] == 100.0  # 4 < 4.5

    def test_boundary_total_five_goals(self):
        result = calc_consensus([{"home": 4, "away": 1}])
        assert result["over_under_45"]["over"] == 100.0  # 5 > 4.5

    def test_goalless_score_hits_under_05(self):
        result = calc_consensus([{"home": 0, "away": 0}])
        assert result["over_under_05"]["under"] == 100.0  # 0 < 0.5
        assert result["btts"]["no"] == 100.0
        assert result["result"]["draw"] == 100.0

    def test_missing_home_key_defaults_to_zero(self):
        result = calc_consensus([{"away": 2}])
        assert result["result"]["away"] == 100.0  # 0 < 2

    def test_missing_away_key_defaults_to_zero(self):
        result = calc_consensus([{"home": 1}])
        assert result["result"]["home"] == 100.0

    def test_none_values_treated_as_zero(self):
        result = calc_consensus([{"home": None, "away": None}])
        assert result["result"]["draw"] == 100.0  # 0 == 0
        assert result["over_under_05"]["under"] == 100.0

    def test_exception_mid_list_returns_empty_structure(self):
        # First entry is valid, second raises inside the loop ("boom" + "bang"
        # compared against 2.5 raises TypeError) -> partial results discarded.
        scores = [{"home": 2, "away": 1}, {"home": "boom", "away": "bang"}]
        assert calc_consensus(scores) == empty_consensus()


# -- calc_consensus: properties (hypothesis) -------------------------------------


class TestCalcConsensusProperties:
    @settings(deadline=None)
    @given(scores=SCORE_LISTS)
    def test_property_result_percentages_sum_to_100(self, scores):
        result = calc_consensus(scores)
        total = sum(result["result"].values())
        assert total == pytest.approx(100.0, abs=0.2)

    @settings(deadline=None)
    @given(scores=SCORE_LISTS)
    def test_property_over_under_complement_per_line(self, scores):
        result = calc_consensus(scores)
        for market in OVER_UNDER_MARKETS:
            total = result[market]["over"] + result[market]["under"]
            assert total == pytest.approx(100.0, abs=0.15), market

    @settings(deadline=None)
    @given(scores=SCORE_LISTS)
    def test_property_btts_complement(self, scores):
        result = calc_consensus(scores)
        total = result["btts"]["yes"] + result["btts"]["no"]
        assert total == pytest.approx(100.0, abs=0.15)

    @settings(deadline=None)
    @given(scores=SCORE_LISTS)
    def test_property_all_values_within_0_100(self, scores):
        for value in flat_values(calc_consensus(scores)):
            assert 0.0 <= value <= 100.0

    @settings(deadline=None)
    @given(scores=SINGLE_SCORE)
    def test_property_single_source_is_degenerate(self, scores):
        # With one source every percentage must be exactly 0.0 or 100.0.
        for value in flat_values(calc_consensus(scores)):
            assert value in (0.0, 100.0)

    @settings(deadline=None)
    @given(scores=SCORE_LISTS)
    def test_property_double_chance_pairwise_covers_all_scores(self, scores):
        result = calc_consensus(scores)
        dc = result["double_chance"]
        # 1X + 12 covers home wins, draws and away wins; same for X2 + 12.
        assert dc["1x"] + dc["12"] >= 100.0 - 0.15
        assert dc["x2"] + dc["12"] >= 100.0 - 0.15


# -- adjusted_consensus (Bayesian shrinkage, lives in scoring.py) -----------------


class TestAdjustedConsensus:
    def test_formula_single_source_default_k(self):
        # 50 + (1 / (1 + 3)) * (80 - 50) = 50 + 0.25 * 30 = 57.5
        assert adjusted_consensus(80.0, 1, 3.0) == pytest.approx(57.5)

    def test_formula_below_fifty(self):
        # 50 + 0.25 * (20 - 50) = 42.5
        assert adjusted_consensus(20.0, 1, 3.0) == pytest.approx(42.5)

    def test_zero_sources_returns_neutral_fifty(self):
        assert adjusted_consensus(80.0, 0, 3.0) == 50.0
        assert adjusted_consensus(20.0, 0, 5.0) == 50.0

    def test_at_fifty_stays_fifty_for_any_inputs(self):
        assert adjusted_consensus(50.0, 0, 3.0) == 50.0
        assert adjusted_consensus(50.0, 7, 10.0) == 50.0

    def test_high_source_count_converges_to_raw(self):
        # 10000 sources, k=3: weight = 10000/10003 = 0.9997 -> 89.988.
        assert adjusted_consensus(90.0, 10000, 3.0) == pytest.approx(90.0, abs=0.05)

    def test_larger_k_shrinks_harder_toward_fifty(self):
        raw, sources = 90.0, 2
        distances = []
        for k in (1.0, 3.0, 10.0, 100.0):
            adjusted = adjusted_consensus(raw, sources, k)
            distances.append(abs(adjusted - 50.0))
        assert distances == sorted(distances, reverse=True)
        assert all(d > 0 for d in distances)

    @settings(deadline=None)
    @given(
        raw=st.floats(min_value=0.0, max_value=100.0),
        sources=st.integers(min_value=0, max_value=200),
        k=st.floats(min_value=0.5, max_value=10.0),
    )
    def test_property_shrinkage_never_amplifies_distance_from_fifty(
        self, raw, sources, k
    ):
        adjusted = adjusted_consensus(raw, sources, k)
        assert abs(adjusted - 50.0) <= abs(raw - 50.0) + 1e-9
        low, high = min(50.0, raw), max(50.0, raw)
        assert low - 1e-9 <= adjusted <= high + 1e-9

    @settings(deadline=None)
    @given(
        raw=st.floats(min_value=0.0, max_value=100.0),
        k=st.floats(min_value=0.5, max_value=10.0),
        s1=st.integers(min_value=0, max_value=100),
        s2=st.integers(min_value=0, max_value=100),
    )
    def test_property_more_sources_move_closer_to_raw(self, raw, k, s1, s2):
        lo, hi = sorted((s1, s2))
        near = adjusted_consensus(raw, lo, k)
        far = adjusted_consensus(raw, hi, k)
        assert abs(near - raw) >= abs(far - raw) - 1e-9
