"""[P1] Pure unit tests for analytics router helpers.

Branch-level coverage of every private helper in routers/analytics.py.
"""

from datetime import datetime, timedelta, timezone

from conftest import make_leg, make_slip
from core.analytics_utils import calculate_daily_summary
from routers.analytics import (
    _correlation_matrix,
    _drawdown_data,
    _league_breakdown,
    _market_breakdown,
    _pnl_by_market,
    _predict_outcome_from_score,
    _profile_scatter,
    _recency_weight,
    _source_breakdown,
    _source_market_correlation,
    _trust_score,
    _wilson_lower_bound,
)


class TestDrawdownData:
    def test_empty_history_returns_empty_list(self) -> None:
        assert _drawdown_data([]) == []

    def test_peak_tracking_and_drawdown_rounding(self) -> None:
        history = [
            {"date": "d1", "cumulative_profit": 5.0},
            {"date": "d2", "cumulative_profit": 8.0},
            {"date": "d3", "cumulative_profit": 2.0},
        ]
        out = _drawdown_data(history)
        assert out[0] == {
            "date": "d1",
            "drawdown": 0.0,
            "peak": 5.0,
            "cumulative_profit": 5.0,
        }
        assert out[1]["peak"] == 8.0
        assert out[1]["drawdown"] == 0.0
        assert out[2]["drawdown"] == -6.0
        assert out[2]["peak"] == 8.0


class TestBankrollHistory:
    def test_history_adds_profit_to_first_settled_stake(self) -> None:
        slips = [
            make_slip(
                slip_id=1,
                date_generated="2030-01-01T10:00:00",
                units=1.0,
                total_odds=2.0,
                slip_status="Won",
            ),
            make_slip(
                slip_id=2,
                date_generated="2030-01-02T10:00:00",
                units=1.0,
                total_odds=2.0,
                slip_status="Lost",
            ),
        ]

        history = calculate_daily_summary(slips)

        assert [row["bankroll"] for row in history] == [2.0, 1.0]


class TestPredictOutcomeFromScore:
    def test_result_market(self) -> None:
        assert _predict_outcome_from_score(2, 1, "1", "result") == "HOME"
        assert _predict_outcome_from_score(1, 1, "X", "result") == "DRAW"
        assert _predict_outcome_from_score(0, 2, "2", "result") == "AWAY"

    def test_over_under_markets(self) -> None:
        assert _predict_outcome_from_score(2, 1, "Over 2.5", "over_under_25") == "OVER_25"
        assert _predict_outcome_from_score(0, 2, "Under 2.5", "over_under_25") == "UNDER_25"
        assert _predict_outcome_from_score(2, 0, "Over 1.5", "over_under_15") == "OVER_15"
        assert _predict_outcome_from_score(1, 0, "Under 1.5", "over_under_15") == "UNDER_15"
        assert _predict_outcome_from_score(1, 0, "Over 0.5", "over_under_05") == "OVER_05"
        assert _predict_outcome_from_score(0, 0, "Under 0.5", "over_under_05") == "UNDER_05"
        assert _predict_outcome_from_score(4, 0, "Over 3.5", "over_under_35") == "OVER_35"
        assert _predict_outcome_from_score(1, 2, "Under 3.5", "over_under_35") == "UNDER_35"
        assert _predict_outcome_from_score(3, 2, "Over 4.5", "over_under_45") == "OVER_45"
        assert _predict_outcome_from_score(2, 2, "Under 4.5", "over_under_45") == "UNDER_45"

    def test_btts_market(self) -> None:
        assert _predict_outcome_from_score(1, 1, "BTTS Yes", "btts") == "BTTS_YES"
        assert _predict_outcome_from_score(2, 0, "BTTS No", "btts") == "BTTS_NO"

    def test_double_chance_market(self) -> None:
        assert _predict_outcome_from_score(2, 1, "1X", "double_chance") == "DC_1X"
        assert _predict_outcome_from_score(1, 1, "X2", "double_chance") == "DC_X2"
        assert _predict_outcome_from_score(1, 2, "12", "double_chance") == "DC_12"

    def test_unknown_market_type_returns_unknown(self) -> None:
        assert _predict_outcome_from_score(1, 1, "Whatever", "not_a_type") == "UNKNOWN"


class TestMarketBreakdown:
    def _won_slip(self, legs, units=2.0):
        return make_slip(units=units, legs=legs)

    def test_aggregates_and_dedupes_by_fingerprint(self) -> None:
        dup_url = "https://x.com/1"
        legs = [
            make_leg(market="1", odds=2.0, status="Won", result_url=dup_url),
            make_leg(market="1", odds=2.0, status="Won", result_url=dup_url),  # duplicate prediction
            make_leg(market="Over 2.5", odds=3.0, status="Lost", result_url="https://x.com/2"),
        ]
        out = _market_breakdown([self._won_slip(legs, units=3.0)])
        by_market = {r["market"]: r for r in out}
        # Dup leg counted once but profit aggregated twice
        assert by_market["1"]["legs"] == 1
        assert by_market["1"]["won"] == 1
        # per_leg_stake = 3.0 / 3 = 1.0 → profit (2.0-1)*1.0*2 = 2.0
        assert by_market["1"]["net_profit"] == 2.0
        assert by_market["Over 2.5"]["lost"] == 1
        assert by_market["Over 2.5"]["net_profit"] == -1.0

    def test_pending_legs_ignored(self) -> None:
        legs = [make_leg(status="Pending"), make_leg(status="Live")]
        assert _market_breakdown([make_slip(legs=legs)]) == []

    def test_unsettled_slips_ignored(self) -> None:
        slip = make_slip(slip_status="Pending")
        assert _market_breakdown([slip]) == []

    def test_edge_sorting_desc(self) -> None:
        legs = [
            make_leg(market="LowEdge", odds=1.1, status="Won", result_url="https://x.com/a"),
            make_leg(market="HighEdge", odds=10.0, status="Won", result_url="https://x.com/b"),
        ]
        out = _market_breakdown([make_slip(legs=legs)])
        assert out[0]["market"] == "HighEdge"

    def test_implied_and_avg_odds_computed(self) -> None:
        legs = [make_leg(market="1", odds=2.0, status="Won", result_url="https://x.com/a")]
        out = _market_breakdown([make_slip(legs=legs)])[0]
        assert out["implied_win_rate"] == 50.0
        assert out["win_rate"] == 100.0
        assert out["edge"] == 50.0
        assert out["avg_odds"] == 2.0

    def test_zero_leg_slip_per_leg_stake_guard(self) -> None:
        slip = make_slip(slip_status="Won", legs=[])
        out = _market_breakdown([slip])
        assert out == []


class TestLeagueBreakdown:
    def test_missing_league_becomes_unknown(self) -> None:
        legs = [make_leg(status="Won", league=None)]
        out = _league_breakdown([make_slip(legs=legs)])
        assert out[0]["league"] == "Unknown"

    def test_dedup_and_profit(self) -> None:
        url = "https://x.com/1"
        legs = [
            make_leg(market="1", odds=2.0, status="Won", result_url=url, league="La Liga"),
            make_leg(market="1", odds=2.0, status="Won", result_url=url, league="La Liga"),
        ]
        out = _league_breakdown([make_slip(legs=legs, units=2.0)])
        assert out[0]["legs"] == 1
        assert out[0]["won"] == 1
        assert out[0]["net_profit"] == 2.0

    def test_zero_odds_implied_zero(self) -> None:
        legs = [make_leg(status="Won", odds=0.0)]
        out = _league_breakdown([make_slip(legs=legs)])
        assert out[0]["implied_win_rate"] == 0.0


class TestSourceMarketCorrelation:
    def _pred_slip(self, **leg_over):
        leg = make_leg(
            market="1",
            market_type="result",
            final_score="2:1",
            predictions=[
                {"source": "forebet", "home": 2, "away": 1},
                {"source": "xgscore", "home": 0, "away": 0},
            ],
            **leg_over,
        )
        return make_slip(legs=[leg])

    def test_matrix_accuracy_computed(self) -> None:
        out = _source_market_correlation([self._pred_slip()])
        assert out["sources"] == ["forebet", "xgscore"]
        assert out["markets"] == ["result"]
        assert out["matrix"]["forebet"]["result"] == {"accuracy": 100.0, "total": 1}
        assert out["matrix"]["xgscore"]["result"] == {"accuracy": 0.0, "total": 1}

    def test_legs_without_predictions_skipped(self) -> None:
        slip = make_slip(legs=[make_leg(predictions=[], final_score="2:1")])
        assert _source_market_correlation([slip]) == {
            "sources": [],
            "markets": [],
            "matrix": {},
        }

    def test_legs_without_final_score_skipped(self) -> None:
        slip = make_slip(legs=[make_leg(final_score=None)])
        assert _source_market_correlation([slip]) == {
            "sources": [],
            "markets": [],
            "matrix": {},
        }

    def test_malformed_final_score_skipped(self) -> None:
        slip = make_slip(legs=[make_leg(final_score="not:numeric")])
        assert _source_market_correlation([slip]) == {
            "sources": [],
            "markets": [],
            "matrix": {},
        }


class TestSourceBreakdown:
    def _slip(self, home, away, final="2:1"):
        leg = make_leg(
            market="Over 2.5",
            market_type="over_under_25",
            final_score=final,
            predictions=[{"source": "forebet", "home": home, "away": away}],
        )
        return make_slip(legs=[leg])

    def test_accuracy_and_mae(self) -> None:
        out = _source_breakdown([self._slip(2, 1)])
        assert len(out) == 1
        src = out[0]
        assert src["source"] == "forebet"
        assert src["total_predictions"] == 1
        assert src["correct_predictions"] == 1
        assert src["accuracy"] == 100.0
        assert src["score_mae"] == 0.0
        assert src["markets"][0]["accuracy"] == 100.0

    def test_mae_computed_for_wrong_score(self) -> None:
        out = _source_breakdown([self._slip(5, 0, final="2:1")])
        assert out[0]["score_mae"] == 2.0
        assert out[0]["accuracy"] == 100.0

    def test_malformed_score_leg_skipped(self) -> None:
        slip = self._slip(2, 1)
        slip.legs[0].final_score = "bad"
        assert _source_breakdown([slip]) == []

    def test_missing_predictions_skipped(self) -> None:
        slip = make_slip(legs=[make_leg(predictions=[], final_score="2:1")])
        assert _source_breakdown([slip]) == []

    def test_sorted_by_accuracy_desc(self) -> None:
        good = self._slip(2, 1)
        bad_leg = make_leg(
            market="Under 2.5",
            market_type="over_under_25",
            final_score="3:0",
            predictions=[{"source": "weak", "home": 0, "away": 0}],
        )
        bad = make_slip(legs=[bad_leg])
        out = _source_breakdown([good, bad])
        assert out[0]["source"] == "forebet"

    def test_trust_fields_present(self) -> None:
        out = _source_breakdown([self._slip(2, 1)])
        src = out[0]
        assert "trust_score" in src
        assert "recency_weight" in src
        assert "latest_prediction_date" in src
        assert isinstance(src["trust_score"], float)
        assert 0.0 <= src["trust_score"] <= 1.0
        assert src["recency_weight"] in (0.2, 0.5, 0.8, 1.0)

    def test_zero_predictions_no_source(self) -> None:
        # A slip with no predictions yields no source rows at all
        slip = make_slip(legs=[make_leg(predictions=[], final_score="2:1")])
        assert _source_breakdown([slip]) == []

    def test_single_prediction_trust(self) -> None:
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        slip = make_slip(
            date_generated=recent,
            legs=[
                make_leg(
                    market="Over 2.5",
                    market_type="over_under_25",
                    final_score="2:1",
                    predictions=[{"source": "s", "home": 2, "away": 1}],
                )
            ],
        )
        out = _source_breakdown([slip])
        # n=1, c=1 → wilson lower bound ~0.344, recency 1.0
        assert out[0]["total_predictions"] == 1
        assert out[0]["correct_predictions"] == 1
        assert out[0]["recency_weight"] == 1.0
        assert out[0]["trust_score"] == round(_wilson_lower_bound(1, 1) * 1.0, 6)

    def test_perfect_vs_poor_accuracy(self) -> None:
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        perfect = make_slip(
            date_generated=recent,
            legs=[
                make_leg(
                    market="Over 2.5",
                    market_type="over_under_25",
                    final_score="2:1",
                    predictions=[{"source": "good", "home": 2, "away": 1}],
                )
            ],
        )
        poor = make_slip(
            slip_id=2,
            date_generated=recent,
            legs=[
                make_leg(
                    market="Over 2.5",
                    market_type="over_under_25",
                    final_score="0:0",
                    predictions=[{"source": "bad", "home": 3, "away": 2}],
                )
            ],
        )
        out = {r["source"]: r for r in _source_breakdown([perfect, poor])}
        assert out["good"]["trust_score"] > out["bad"]["trust_score"]
        assert out["bad"]["correct_predictions"] == 0

    def test_sample_size_shrinks_same_accuracy(self) -> None:
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        # 1/1 vs 10/10 — same accuracy, smaller sample gets lower wilson bound
        small = make_slip(
            date_generated=recent,
            legs=[
                make_leg(
                    market="Over 2.5",
                    market_type="over_under_25",
                    final_score="2:1",
                    predictions=[{"source": "small", "home": 2, "away": 1}],
                )
            ],
        )
        big_legs = [
            make_leg(
                market="Over 2.5",
                market_type="over_under_25",
                final_score="2:1",
                result_url=f"https://x/{i}",
                predictions=[{"source": "big", "home": 2, "away": 1}],
            )
            for i in range(10)
        ]
        big = make_slip(slip_id=2, date_generated=recent, legs=big_legs)
        out = {r["source"]: r for r in _source_breakdown([small, big])}
        assert out["big"]["trust_score"] > out["small"]["trust_score"]

    def test_missing_date_uses_oldest_bucket(self) -> None:
        # slip without date_generated → latest_date None → recency 0.2
        slip = make_slip(
            date_generated=None,
            legs=[
                make_leg(
                    market="Over 2.5",
                    market_type="over_under_25",
                    final_score="2:1",
                    predictions=[{"source": "nodate", "home": 2, "away": 1}],
                )
            ],
        )
        out = _source_breakdown([slip])
        assert out[0]["recency_weight"] == 0.2
        assert out[0]["latest_prediction_date"] is None
        assert out[0]["trust_score"] == round(_wilson_lower_bound(1, 1) * 0.2, 6)

    def test_latest_prediction_date_tracked(self) -> None:
        old = "2026-01-01T10:00:00"
        new = "2026-11-01T10:00:00"
        s1 = make_slip(
            slip_id=1,
            date_generated=old,
            legs=[
                make_leg(
                    market="Over 2.5",
                    market_type="over_under_25",
                    final_score="2:1",
                    result_url="https://x/1",
                    predictions=[{"source": "src", "home": 2, "away": 1}],
                )
            ],
        )
        s2 = make_slip(
            slip_id=2,
            date_generated=new,
            legs=[
                make_leg(
                    market="Over 2.5",
                    market_type="over_under_25",
                    final_score="2:1",
                    result_url="https://x/2",
                    predictions=[{"source": "src", "home": 2, "away": 1}],
                )
            ],
        )
        out = _source_breakdown([s1, s2])
        assert out[0]["latest_prediction_date"] == "2026-11-01"
        assert out[0]["total_predictions"] == 2


class TestTrustScoreHelpers:
    def test_wilson_zero_n(self) -> None:
        assert _wilson_lower_bound(0, 0) == 0.0

    def test_wilson_perfect(self) -> None:
        # 10/10 lower bound < 1.0 (uncertainty), but > 0.7
        lb = _wilson_lower_bound(10, 10)
        assert 0.7 < lb < 1.0

    def test_wilson_zero_correct(self) -> None:
        assert _wilson_lower_bound(0, 10) == 0.0

    def test_wilson_monotonic_in_n(self) -> None:
        # same accuracy, more samples → higher lower bound
        assert _wilson_lower_bound(5, 5) < _wilson_lower_bound(50, 50)

    def test_wilson_bounded(self) -> None:
        for c in range(0, 20):
            for n in range(1, 30):
                lb = _wilson_lower_bound(c, n)
                assert 0.0 <= lb <= 1.0

    def test_recency_boundaries(self) -> None:
        now = datetime.now(timezone.utc)
        d3 = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")
        d6 = (now - timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%S")
        d7 = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
        d29 = (now - timedelta(days=29)).strftime("%Y-%m-%dT%H:%M:%S")
        d30 = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
        d89 = (now - timedelta(days=89)).strftime("%Y-%m-%dT%H:%M:%S")
        d90 = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S")
        d200 = (now - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%S")
        assert _recency_weight(d3) == 1.0
        assert _recency_weight(d6) == 1.0
        assert _recency_weight(d7) == 0.8
        assert _recency_weight(d29) == 0.8
        assert _recency_weight(d30) == 0.5
        assert _recency_weight(d89) == 0.5
        assert _recency_weight(d90) == 0.2
        assert _recency_weight(d200) == 0.2
        assert _recency_weight(None) == 0.2
        assert _recency_weight("not-a-date") == 0.2

    def test_trust_score_deterministic(self) -> None:
        ts1, rw1 = _trust_score(7, 10, "2026-11-10T00:00:00")
        ts2, rw2 = _trust_score(7, 10, "2026-11-10T00:00:00")
        assert ts1 == ts2
        assert rw1 == rw2
        assert 0.0 <= ts1 <= 1.0


class TestPnlByMarket:
    def test_dedup_counts_aggregate_profit(self) -> None:
        url = "https://x.com/1"
        legs = [
            make_leg(market="1", odds=2.0, status="Won", result_url=url),
            make_leg(market="1", odds=2.0, status="Won", result_url=url),
        ]
        out = _pnl_by_market([make_slip(legs=legs, units=2.0)])
        assert out[0]["market"] == "1"
        assert out[0]["won"] == 1
        assert out[0]["lost"] == 0
        assert out[0]["net_profit"] == 2.0

    def test_sorted_by_abs_net_profit(self) -> None:
        legs = [
            make_leg(market="Small", odds=1.5, status="Won", result_url="https://x.com/a"),
            make_leg(market="Big", odds=10.0, status="Lost", result_url="https://x.com/b"),
        ]
        out = _pnl_by_market([make_slip(legs=legs, units=2.0)])
        assert out[0]["market"] == "Big"


class TestProfileScatter:
    def test_scatter_metrics(self) -> None:
        slips = [
            make_slip(profile="safe", slip_status="Won", total_odds=2.0, units=1.0),
            make_slip(profile="safe", slip_status="Lost", total_odds=4.0, units=1.0, slip_id=2),
        ]
        out = _profile_scatter(slips)
        assert len(out) == 1
        p = out[0]
        assert p["profile"] == "safe"
        assert p["volume"] == 2
        assert p["avg_odds"] == 3.0
        assert p["win_rate"] == 50.0
        assert p["net_profit"] == 0.0
        assert p["break_even_win_rate"] == 33.3

    def test_pending_slips_excluded(self) -> None:
        slips = [make_slip(profile="p", slip_status="Pending")]
        assert _profile_scatter(slips) == []

    def test_multiple_profiles_separated(self) -> None:
        slips = [
            make_slip(profile="a", slip_status="Won"),
            make_slip(profile="b", slip_status="Lost", slip_id=2),
        ]
        out = _profile_scatter(slips)
        assert {r["profile"] for r in out} == {"a", "b"}


class TestCorrelationMatrix:
    def test_matrix_structure_and_dedup(self) -> None:
        url = "https://x.com/1"
        legs = [
            make_leg(market="1", odds=2.0, status="Won", league="La Liga", result_url=url),
            make_leg(market="1", odds=2.0, status="Won", league="La Liga", result_url=url),
            make_leg(
                market="X",
                odds=3.0,
                status="Lost",
                league="Serie A",
                result_url="https://x.com/2",
            ),
        ]
        out = _correlation_matrix([make_slip(legs=legs)])
        assert out["leagues"] == ["La Liga", "Serie A"]
        assert out["markets"] == ["1", "X"]
        cell = out["matrix"]["La Liga"]["1"]
        assert cell["total"] == 1
        assert cell["win_rate"] == 100.0
        assert cell["edge"] == 50.0

    def test_zero_odds_implied_zero(self) -> None:
        legs = [make_leg(status="Won", odds=0.0)]
        out = _correlation_matrix([make_slip(legs=legs)])
        assert out["matrix"]["La Liga"]["1"]["edge"] == 100.0

    def test_empty_slips(self) -> None:
        out = _correlation_matrix([])
        assert out == {"leagues": [], "markets": [], "matrix": {}}
