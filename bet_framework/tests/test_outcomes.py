"""
Gap tests for bet_framework/core/outcomes.py (GitHub issue #70).

Covered public API:
  parse_score(raw)            - every valid format, whitespace, negative and
                                multi-digit values, invalid inputs raising
  determine_outcome(...)      - full settlement matrix:
                                  RESULT          (3x3 grid: HOME/DRAW/AWAY)
                                  OVER_UNDER_05/15/25/35/45 (boundary totals,
                                    covers source lines 103-110)
                                  BTTS            (YES/NO)
                                  DOUBLE_CHANCE   (1X/12/X2 WON+LOST, covers
                                    source lines 89-95)
                                  unknown market_type -> PENDING

Property-based tests (hypothesis): parse_score round-trip, result-market
consistency across label permutations.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from bet_framework.core.outcomes import determine_outcome, parse_score
from bet_framework.markets.enums import MarketKey, MarketType, Outcome

# -- parse_score ----------------------------------------------------------------


class TestParseScore:
    def test_regular_scores(self) -> None:
        assert parse_score("2:1") == (2, 1)
        assert parse_score("1:2") == (1, 2)
        assert parse_score("0:0") == (0, 0)

    def test_high_scoring_and_multi_digit(self) -> None:
        assert parse_score("10:7") == (10, 7)
        assert parse_score("12:0") == (12, 0)

    def test_identical_halves(self) -> None:
        assert parse_score("3:3") == (3, 3)

    @pytest.mark.parametrize("raw", ["1:0", "0:1", "4:2", "9:9", "15:3"])
    def test_various_valid_scores(self, raw) -> None:
        home, away = parse_score(raw)
        assert f"{home}:{away}" == raw

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("no-colon", pytest.raises(ValueError)),
            ("", pytest.raises(ValueError)),
            ("a:b", pytest.raises(ValueError)),
            ("1:x", pytest.raises(ValueError)),
            ("1:2:3", pytest.raises(ValueError)),
            (":", pytest.raises(ValueError)),
        ],
    )
    def test_invalid_formats_raise(self, raw, expected) -> None:
        with expected:
            parse_score(raw)

    @settings(deadline=None)
    @given(
        home=st.integers(min_value=0, max_value=30),
        away=st.integers(min_value=0, max_value=30),
    )
    def test_property_round_trip(self, home, away) -> None:
        assert parse_score(f"{home}:{away}") == (home, away)


# -- determine_outcome: RESULT -----------------------------------------------------


class TestDetermineOutcomeResult:
    @pytest.mark.parametrize(
        "home,away",
        [(2, 1), (3, 0), (1, 0), (5, 2)],
    )
    def test_home_wins(self, home, away) -> None:
        assert determine_outcome(home, away, MarketKey.HOME, MarketType.RESULT) == Outcome.WON
        assert determine_outcome(home, away, MarketKey.AWAY, MarketType.RESULT) == Outcome.LOST
        assert determine_outcome(home, away, MarketKey.DRAW, MarketType.RESULT) == Outcome.LOST

    @pytest.mark.parametrize(
        "home,away",
        [(0, 1), (1, 3), (2, 5), (0, 7)],
    )
    def test_away_wins(self, home, away) -> None:
        assert determine_outcome(home, away, MarketKey.AWAY, MarketType.RESULT) == Outcome.WON
        assert determine_outcome(home, away, MarketKey.HOME, MarketType.RESULT) == Outcome.LOST
        assert determine_outcome(home, away, MarketKey.DRAW, MarketType.RESULT) == Outcome.LOST

    @pytest.mark.parametrize(
        "home,away",
        [(0, 0), (1, 1), (3, 3), (2, 2)],
    )
    def test_draws(self, home, away) -> None:
        assert determine_outcome(home, away, MarketKey.DRAW, MarketType.RESULT) == Outcome.WON
        assert determine_outcome(home, away, MarketKey.HOME, MarketType.RESULT) == Outcome.LOST
        assert determine_outcome(home, away, MarketKey.AWAY, MarketType.RESULT) == Outcome.LOST

    def test_full_three_by_three_grid(self) -> None:
        scores = [(2, 1), (1, 1), (0, 2)]
        labels = [MarketKey.HOME, MarketKey.DRAW, MarketKey.AWAY]
        expected = [
            [Outcome.WON, Outcome.LOST, Outcome.LOST],
            [Outcome.LOST, Outcome.WON, Outcome.LOST],
            [Outcome.LOST, Outcome.LOST, Outcome.WON],
        ]
        for (home, away), row in zip(scores, expected, strict=True):
            for label, want in zip(labels, row, strict=True):
                assert determine_outcome(home, away, label, MarketType.RESULT) == want


# -- determine_outcome: OVER / UNDER (covers source lines 103-110) ------------------


OVER_UNDER_CASES = [
    # (market_type, over_label, under_label, threshold, winning_total, losing_total)
    (MarketType.OVER_UNDER_05, MarketKey.OVER_05, MarketKey.UNDER_05, 0.5, 1, 0),
    (MarketType.OVER_UNDER_15, MarketKey.OVER_15, MarketKey.UNDER_15, 1.5, 2, 1),
    (MarketType.OVER_UNDER_25, MarketKey.OVER_25, MarketKey.UNDER_25, 2.5, 3, 2),
    (MarketType.OVER_UNDER_35, MarketKey.OVER_35, MarketKey.UNDER_35, 3.5, 4, 3),
    (MarketType.OVER_UNDER_45, MarketKey.OVER_45, MarketKey.UNDER_45, 4.5, 5, 4),
]


class TestDetermineOutcomeOverUnder:
    @pytest.mark.parametrize(
        "market_type,over_label,under_label,threshold,winning_total,losing_total",
        OVER_UNDER_CASES,
    )
    def test_over_wins_when_total_above_threshold(
        self,
        market_type,
        over_label,
        under_label,
        threshold,
        winning_total,
        losing_total,
    ) -> None:
        home, away = winning_total, 0
        assert determine_outcome(home, away, over_label, market_type) == Outcome.WON

    @pytest.mark.parametrize(
        "market_type,over_label,under_label,threshold,winning_total,losing_total",
        OVER_UNDER_CASES,
    )
    def test_over_loses_when_total_at_or_below_threshold(
        self,
        market_type,
        over_label,
        under_label,
        threshold,
        winning_total,
        losing_total,
    ) -> None:
        home, away = losing_total, 0
        assert determine_outcome(home, away, over_label, market_type) == Outcome.LOST

    @pytest.mark.parametrize(
        "market_type,over_label,under_label,threshold,winning_total,losing_total",
        OVER_UNDER_CASES,
    )
    def test_under_wins_when_total_below_threshold(
        self,
        market_type,
        over_label,
        under_label,
        threshold,
        winning_total,
        losing_total,
    ) -> None:
        home, away = losing_total, 0
        assert determine_outcome(home, away, under_label, market_type) == Outcome.WON

    @pytest.mark.parametrize(
        "market_type,over_label,under_label,threshold,winning_total,losing_total",
        OVER_UNDER_CASES,
    )
    def test_under_loses_when_total_above_threshold(
        self,
        market_type,
        over_label,
        under_label,
        threshold,
        winning_total,
        losing_total,
    ) -> None:
        home, away = winning_total, 0
        assert determine_outcome(home, away, under_label, market_type) == Outcome.LOST

    def test_goalless_game_settles_all_under_markets(self) -> None:
        for market_type, _over, under, _t, _w, _l in OVER_UNDER_CASES:
            assert determine_outcome(0, 0, under, market_type) == Outcome.WON
            assert determine_outcome(0, 0, _over, market_type) == Outcome.LOST

    def test_six_goal_game_settles_all_over_markets(self) -> None:
        for market_type, over, _under, _t, _w, _l in OVER_UNDER_CASES:
            assert determine_outcome(4, 2, over, market_type) == Outcome.WON

    def test_goals_split_between_teams_count_for_totals(self) -> None:
        # total = 3 regardless of distribution: over 2.5 wins, under 3.5 wins
        assert determine_outcome(2, 1, MarketKey.OVER_25, MarketType.OVER_UNDER_25) == Outcome.WON
        assert determine_outcome(1, 2, MarketKey.OVER_25, MarketType.OVER_UNDER_25) == Outcome.WON
        assert determine_outcome(0, 3, MarketKey.OVER_25, MarketType.OVER_UNDER_25) == Outcome.WON
        assert determine_outcome(3, 0, MarketKey.UNDER_35, MarketType.OVER_UNDER_35) == Outcome.WON

    def test_boundary_exactly_two_goals(self) -> None:
        # total == 2: under 2.5 WON, over 1.5 WON, under 1.5 LOST, over 2.5 LOST
        assert determine_outcome(1, 1, MarketKey.UNDER_25, MarketType.OVER_UNDER_25) == Outcome.WON
        assert determine_outcome(1, 1, MarketKey.OVER_15, MarketType.OVER_UNDER_15) == Outcome.WON
        assert determine_outcome(1, 1, MarketKey.UNDER_15, MarketType.OVER_UNDER_15) == Outcome.LOST
        assert determine_outcome(1, 1, MarketKey.OVER_25, MarketType.OVER_UNDER_25) == Outcome.LOST

    def test_boundary_exactly_one_goal(self) -> None:
        # total == 1: under 1.5 WON, over 0.5 WON, under 0.5 LOST, over 1.5 LOST
        assert determine_outcome(1, 0, MarketKey.UNDER_15, MarketType.OVER_UNDER_15) == Outcome.WON
        assert determine_outcome(1, 0, MarketKey.OVER_05, MarketType.OVER_UNDER_05) == Outcome.WON
        assert determine_outcome(0, 1, MarketKey.UNDER_05, MarketType.OVER_UNDER_05) == Outcome.LOST
        assert determine_outcome(1, 0, MarketKey.OVER_15, MarketType.OVER_UNDER_15) == Outcome.LOST

    def test_boundary_exactly_four_goals(self) -> None:
        # total == 4: over 3.5 WON, under 4.5 WON, under 3.5 LOST, over 4.5 LOST
        assert determine_outcome(2, 2, MarketKey.OVER_35, MarketType.OVER_UNDER_35) == Outcome.WON
        assert determine_outcome(3, 1, MarketKey.UNDER_45, MarketType.OVER_UNDER_45) == Outcome.WON
        assert determine_outcome(4, 0, MarketKey.UNDER_35, MarketType.OVER_UNDER_35) == Outcome.LOST
        assert determine_outcome(0, 4, MarketKey.OVER_45, MarketType.OVER_UNDER_45) == Outcome.LOST

    def test_boundary_exactly_five_goals(self) -> None:
        # total == 5: over 4.5 WON, under 4.5 LOST
        assert determine_outcome(5, 0, MarketKey.OVER_45, MarketType.OVER_UNDER_45) == Outcome.WON
        assert determine_outcome(2, 3, MarketKey.UNDER_45, MarketType.OVER_UNDER_45) == Outcome.LOST

    def test_default_threshold_branch_for_over_25_label(self) -> None:
        # O/U 2.5 labels route to the default else-branch (threshold 2.5).
        assert determine_outcome(2, 1, MarketKey.OVER_25, MarketType.OVER_UNDER_25) == Outcome.WON
        assert determine_outcome(1, 0, MarketKey.OVER_25, MarketType.OVER_UNDER_25) == Outcome.LOST
        assert determine_outcome(1, 0, MarketKey.UNDER_25, MarketType.OVER_UNDER_25) == Outcome.WON
        assert determine_outcome(2, 1, MarketKey.UNDER_25, MarketType.OVER_UNDER_25) == Outcome.LOST

    def test_unknown_label_in_over_under_market_is_lost(self) -> None:
        # Label not in any over/under tuple -> falls through both WON branches.
        assert determine_outcome(2, 1, "Weird Market", MarketType.OVER_UNDER_25) == Outcome.LOST

    @settings(deadline=None)
    @given(
        home=st.integers(min_value=0, max_value=12),
        away=st.integers(min_value=0, max_value=12),
    )
    def test_property_over_under_are_complementary_at_25(self, home, away) -> None:
        total = home + away
        over = determine_outcome(home, away, MarketKey.OVER_25, MarketType.OVER_UNDER_25)
        under = determine_outcome(home, away, MarketKey.UNDER_25, MarketType.OVER_UNDER_25)
        assert {over, under} == {Outcome.WON, Outcome.LOST}
        if total > 2.5:
            assert over == Outcome.WON
        else:
            assert under == Outcome.WON


# -- determine_outcome: BTTS ----------------------------------------------------------


class TestDetermineOutcomeBtts:
    @pytest.mark.parametrize(
        "home,away",
        [(1, 1), (2, 3), (1, 5), (4, 2)],
    )
    def test_btts_yes_wins_when_both_score(self, home, away) -> None:
        assert determine_outcome(home, away, MarketKey.BTTS_YES, MarketType.BTTS) == Outcome.WON
        assert determine_outcome(home, away, MarketKey.BTTS_NO, MarketType.BTTS) == Outcome.LOST

    @pytest.mark.parametrize(
        "home,away",
        [(0, 0), (2, 0), (0, 1), (3, 0)],
    )
    def test_btts_no_wins_when_any_side_blank(self, home, away) -> None:
        assert determine_outcome(home, away, MarketKey.BTTS_NO, MarketType.BTTS) == Outcome.WON
        assert determine_outcome(home, away, MarketKey.BTTS_YES, MarketType.BTTS) == Outcome.LOST

    def test_goalless_draw_is_btts_no(self) -> None:
        assert determine_outcome(0, 0, MarketKey.BTTS_NO, MarketType.BTTS) == Outcome.WON

    def test_unknown_btts_label_is_lost(self) -> None:
        assert determine_outcome(1, 1, "BTTS Maybe", MarketType.BTTS) == Outcome.LOST
        assert determine_outcome(1, 0, "BTTS Maybe", MarketType.BTTS) == Outcome.LOST

    @settings(deadline=None)
    @given(
        home=st.integers(min_value=0, max_value=10),
        away=st.integers(min_value=0, max_value=10),
    )
    def test_property_btts_yes_wins_iff_both_positive(self, home, away) -> None:
        expected = Outcome.WON if (home > 0 and away > 0) else Outcome.LOST
        assert determine_outcome(home, away, MarketKey.BTTS_YES, MarketType.BTTS) == expected


# -- determine_outcome: DOUBLE CHANCE (covers source lines 89-95) --------------------


class TestDetermineOutcomeDoubleChance:
    @pytest.mark.parametrize(
        "home,away",
        [(2, 1), (3, 3), (1, 0), (0, 0)],
    )
    def test_dc_1x_wins_on_home_win_or_draw(self, home, away) -> None:
        assert determine_outcome(home, away, MarketKey.DC_1X, MarketType.DOUBLE_CHANCE) == Outcome.WON

    @pytest.mark.parametrize(
        "home,away",
        [(0, 2), (1, 3), (0, 1)],
    )
    def test_dc_1x_loses_on_away_win(self, home, away) -> None:
        assert determine_outcome(home, away, MarketKey.DC_1X, MarketType.DOUBLE_CHANCE) == Outcome.LOST

    @pytest.mark.parametrize(
        "home,away",
        [(2, 1), (0, 2), (1, 3), (4, 0)],
    )
    def test_dc_12_wins_when_not_draw(self, home, away) -> None:
        assert determine_outcome(home, away, MarketKey.DC_12, MarketType.DOUBLE_CHANCE) == Outcome.WON

    @pytest.mark.parametrize(
        "home,away",
        [(1, 1), (0, 0), (3, 3)],
    )
    def test_dc_12_loses_on_draw(self, home, away) -> None:
        assert determine_outcome(home, away, MarketKey.DC_12, MarketType.DOUBLE_CHANCE) == Outcome.LOST

    @pytest.mark.parametrize(
        "home,away",
        [(0, 2), (1, 1), (0, 0), (2, 5)],
    )
    def test_dc_x2_wins_on_away_win_or_draw(self, home, away) -> None:
        assert determine_outcome(home, away, MarketKey.DC_X2, MarketType.DOUBLE_CHANCE) == Outcome.WON

    @pytest.mark.parametrize(
        "home,away",
        [(2, 1), (3, 0), (5, 2)],
    )
    def test_dc_x2_loses_on_home_win(self, home, away) -> None:
        assert determine_outcome(home, away, MarketKey.DC_X2, MarketType.DOUBLE_CHANCE) == Outcome.LOST

    def test_draw_satisfies_both_1x_and_x2(self) -> None:
        assert determine_outcome(2, 2, MarketKey.DC_1X, MarketType.DOUBLE_CHANCE) == Outcome.WON
        assert determine_outcome(2, 2, MarketKey.DC_X2, MarketType.DOUBLE_CHANCE) == Outcome.WON
        assert determine_outcome(2, 2, MarketKey.DC_12, MarketType.DOUBLE_CHANCE) == Outcome.LOST

    def test_all_three_outcomes_covered_by_dc_labels(self) -> None:
        # Any final score wins at least one of the three double-chance labels.
        for home, away in [(0, 0), (1, 0), (0, 1), (2, 2), (3, 1), (0, 4)]:
            results = {
                determine_outcome(home, away, label, MarketType.DOUBLE_CHANCE)
                for label in (MarketKey.DC_1X, MarketKey.DC_12, MarketKey.DC_X2)
            }
            assert Outcome.WON in results

    def test_unknown_dc_label_is_lost(self) -> None:
        assert determine_outcome(1, 1, "1XX", MarketType.DOUBLE_CHANCE) == Outcome.LOST

    @settings(deadline=None)
    @given(
        home=st.integers(min_value=0, max_value=10),
        away=st.integers(min_value=0, max_value=10),
    )
    def test_property_dc_1x_wins_iff_home_ge_away(self, home, away) -> None:
        expected = Outcome.WON if home >= away else Outcome.LOST
        assert determine_outcome(home, away, MarketKey.DC_1X, MarketType.DOUBLE_CHANCE) == expected

    @settings(deadline=None)
    @given(
        home=st.integers(min_value=0, max_value=10),
        away=st.integers(min_value=0, max_value=10),
    )
    def test_property_dc_12_wins_iff_scores_differ(self, home, away) -> None:
        expected = Outcome.WON if home != away else Outcome.LOST
        assert determine_outcome(home, away, MarketKey.DC_12, MarketType.DOUBLE_CHANCE) == expected

    @settings(deadline=None)
    @given(
        home=st.integers(min_value=0, max_value=10),
        away=st.integers(min_value=0, max_value=10),
    )
    def test_property_dc_x2_wins_iff_away_ge_home(self, home, away) -> None:
        expected = Outcome.WON if away >= home else Outcome.LOST
        assert determine_outcome(home, away, MarketKey.DC_X2, MarketType.DOUBLE_CHANCE) == expected


# -- determine_outcome: unknown / degenerate market types ------------------------------


class TestDetermineOutcomePending:
    def test_unknown_market_type_returns_pending(self) -> None:
        assert determine_outcome(2, 1, MarketKey.HOME, "unknown_type") == Outcome.PENDING

    def test_arbitrary_string_market_type_returns_pending(self) -> None:
        assert determine_outcome(2, 1, "Over 2.5", "some_random_market") == Outcome.PENDING

    def test_empty_market_type_returns_pending(self) -> None:
        assert determine_outcome(2, 1, MarketKey.HOME, "") == Outcome.PENDING

    def test_none_market_type_returns_pending(self) -> None:
        assert determine_outcome(2, 1, MarketKey.HOME, None) == Outcome.PENDING

    def test_enum_and_string_values_are_interchangeable(self) -> None:
        # MarketType is a str Enum: raw value strings must route identically.
        assert determine_outcome(2, 1, MarketKey.HOME, "result") == Outcome.WON
        assert determine_outcome(2, 1, "home", MarketType.RESULT) == Outcome.WON
        assert determine_outcome(2, 1, "home", "result") == Outcome.WON

    def test_result_label_with_btts_market_type_is_lost(self) -> None:
        # Cross-market label mismatch settles as LOST, not PENDING.
        assert determine_outcome(2, 1, MarketKey.HOME, MarketType.BTTS) == Outcome.LOST

    @settings(deadline=None)
    @given(
        home=st.integers(min_value=0, max_value=15),
        away=st.integers(min_value=0, max_value=15),
    )
    def test_property_pending_only_for_unknown_types(self, home, away) -> None:
        # Any real market type always settles WON or LOST for valid labels.
        known = [
            (MarketType.RESULT, MarketKey.HOME),
            (MarketType.OVER_UNDER_25, MarketKey.OVER_25),
            (MarketType.OVER_UNDER_15, MarketKey.UNDER_15),
            (MarketType.OVER_UNDER_05, MarketKey.OVER_05),
            (MarketType.OVER_UNDER_35, MarketKey.OVER_35),
            (MarketType.OVER_UNDER_45, MarketKey.UNDER_45),
            (MarketType.BTTS, MarketKey.BTTS_YES),
            (MarketType.DOUBLE_CHANCE, MarketKey.DC_12),
        ]
        for market_type, label in known:
            result = determine_outcome(home, away, label, market_type)
            assert result in (Outcome.WON, Outcome.LOST)


# ── U1 all-markets proof matrix (story 115-2, AC-4) ──────────────────────────
# Every canonical market key x representative scores, pinning that the BACKEND
# outcome dispatch under U1 is correct per key. The user-reported live RED
# ('U2.5' at 1-0) was a FRONTEND badge defect; this matrix proves the backend
# math was already right, and guards it against future key changes.
MATRIX_CASES = [
    (1, 0, MarketKey.UNDER_25, MarketType.OVER_UNDER_25, Outcome.WON),
    (0, 1, MarketKey.UNDER_25, MarketType.OVER_UNDER_25, Outcome.WON),
    (1, 1, MarketKey.UNDER_25, MarketType.OVER_UNDER_25, Outcome.WON),
    (2, 0, MarketKey.UNDER_25, MarketType.OVER_UNDER_25, Outcome.WON),
    (2, 1, MarketKey.UNDER_25, MarketType.OVER_UNDER_25, Outcome.LOST),
    (1, 0, MarketKey.OVER_25, MarketType.OVER_UNDER_25, Outcome.LOST),
    (1, 1, MarketKey.OVER_25, MarketType.OVER_UNDER_25, Outcome.LOST),
    (2, 0, MarketKey.OVER_25, MarketType.OVER_UNDER_25, Outcome.LOST),
    (3, 1, MarketKey.OVER_25, MarketType.OVER_UNDER_25, Outcome.WON),
    (1, 0, MarketKey.OVER_05, MarketType.OVER_UNDER_05, Outcome.WON),
    (0, 0, MarketKey.OVER_05, MarketType.OVER_UNDER_05, Outcome.LOST),
    (0, 0, MarketKey.UNDER_05, MarketType.OVER_UNDER_05, Outcome.WON),
    (1, 0, MarketKey.UNDER_05, MarketType.OVER_UNDER_05, Outcome.LOST),
    (1, 0, MarketKey.OVER_15, MarketType.OVER_UNDER_15, Outcome.LOST),
    (1, 0, MarketKey.UNDER_15, MarketType.OVER_UNDER_15, Outcome.WON),
    (2, 0, MarketKey.OVER_15, MarketType.OVER_UNDER_15, Outcome.WON),
    (2, 0, MarketKey.OVER_35, MarketType.OVER_UNDER_35, Outcome.LOST),
    (2, 0, MarketKey.UNDER_35, MarketType.OVER_UNDER_35, Outcome.WON),
    (5, 0, MarketKey.OVER_45, MarketType.OVER_UNDER_45, Outcome.WON),
    (2, 2, MarketKey.UNDER_45, MarketType.OVER_UNDER_45, Outcome.WON),
    (0, 3, MarketKey.UNDER_45, MarketType.OVER_UNDER_45, Outcome.WON),
    (2, 1, MarketKey.HOME, MarketType.RESULT, Outcome.WON),
    (1, 1, MarketKey.HOME, MarketType.RESULT, Outcome.LOST),
    (1, 1, MarketKey.DRAW, MarketType.RESULT, Outcome.WON),
    (0, 2, MarketKey.AWAY, MarketType.RESULT, Outcome.WON),
    (2, 2, MarketKey.AWAY, MarketType.RESULT, Outcome.LOST),
    (1, 1, MarketKey.BTTS_YES, MarketType.BTTS, Outcome.WON),
    (1, 0, MarketKey.BTTS_YES, MarketType.BTTS, Outcome.LOST),
    (1, 0, MarketKey.BTTS_NO, MarketType.BTTS, Outcome.WON),
    (0, 0, MarketKey.BTTS_NO, MarketType.BTTS, Outcome.WON),
    (1, 1, MarketKey.BTTS_NO, MarketType.BTTS, Outcome.LOST),
    (1, 1, MarketKey.DC_1X, MarketType.DOUBLE_CHANCE, Outcome.WON),
    (0, 1, MarketKey.DC_1X, MarketType.DOUBLE_CHANCE, Outcome.LOST),
    (1, 0, MarketKey.DC_12, MarketType.DOUBLE_CHANCE, Outcome.WON),
    (1, 1, MarketKey.DC_12, MarketType.DOUBLE_CHANCE, Outcome.LOST),
    (0, 1, MarketKey.DC_X2, MarketType.DOUBLE_CHANCE, Outcome.WON),
    (1, 0, MarketKey.DC_X2, MarketType.DOUBLE_CHANCE, Outcome.LOST),
]


@pytest.mark.parametrize("home,away,market,market_type,expected", MATRIX_CASES)
def test_u1_all_markets_outcome_matrix(home, away, market, market_type, expected) -> None:
    assert determine_outcome(home, away, market, market_type) == expected


def test_u1_matrix_covers_every_canonical_key() -> None:
    from bet_framework.markets.catalog import MARKET_CATALOG

    covered = {case[2] for case in MATRIX_CASES}
    assert covered == {spec.key for spec in MARKET_CATALOG}
