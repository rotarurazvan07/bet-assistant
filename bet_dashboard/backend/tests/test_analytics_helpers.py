"""[P1] Pure unit tests for analytics router helpers (issue #58).

Branch-level coverage of every private helper in routers/analytics.py.
"""

from __future__ import annotations

from conftest import make_leg, make_slip
from routers.analytics import (
    _correlation_matrix,
    _drawdown_data,
    _league_breakdown,
    _market_breakdown,
    _pnl_by_market,
    _predict_outcome_from_score,
    _profile_scatter,
    _source_breakdown,
    _source_market_correlation,
)


class TestDrawdownData:
    def test_empty_history_returns_empty_list(self):
        assert _drawdown_data([]) == []

    def test_peak_tracking_and_drawdown_rounding(self):
        history = [
            {"date": "d1", "cumulative_profit": 5.0},
            {"date": "d2", "cumulative_profit": 8.0},
            {"date": "d3", "cumulative_profit": 2.0},
        ]
        out = _drawdown_data(history)
        assert out[0] == {"date": "d1", "drawdown": 0.0, "peak": 5.0, "cumulative_profit": 5.0}
        assert out[1]["peak"] == 8.0
        assert out[1]["drawdown"] == 0.0
        assert out[2]["drawdown"] == -6.0
        assert out[2]["peak"] == 8.0


class TestPredictOutcomeFromScore:
    def test_result_market(self):
        assert _predict_outcome_from_score(2, 1, "1", "result") == "HOME"
        assert _predict_outcome_from_score(1, 1, "X", "result") == "DRAW"
        assert _predict_outcome_from_score(0, 2, "2", "result") == "AWAY"

    def test_over_under_markets(self):
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

    def test_btts_market(self):
        assert _predict_outcome_from_score(1, 1, "BTTS Yes", "btts") == "BTTS_YES"
        assert _predict_outcome_from_score(2, 0, "BTTS No", "btts") == "BTTS_NO"

    def test_double_chance_market(self):
        assert _predict_outcome_from_score(2, 1, "1X", "double_chance") == "DC_1X"
        assert _predict_outcome_from_score(1, 1, "X2", "double_chance") == "DC_X2"
        assert _predict_outcome_from_score(1, 2, "12", "double_chance") == "DC_12"

    def test_unknown_market_type_returns_unknown(self):
        assert _predict_outcome_from_score(1, 1, "Whatever", "not_a_type") == "UNKNOWN"


class TestMarketBreakdown:
    def _won_slip(self, legs, units=2.0):
        return make_slip(units=units, legs=legs)

    def test_aggregates_and_dedupes_by_fingerprint(self):
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

    def test_pending_legs_ignored(self):
        legs = [make_leg(status="Pending"), make_leg(status="Live")]
        assert _market_breakdown([make_slip(legs=legs)]) == []

    def test_unsettled_slips_ignored(self):
        slip = make_slip(slip_status="Pending")
        assert _market_breakdown([slip]) == []

    def test_edge_sorting_desc(self):
        legs = [
            make_leg(market="LowEdge", odds=1.1, status="Won", result_url="https://x.com/a"),
            make_leg(market="HighEdge", odds=10.0, status="Won", result_url="https://x.com/b"),
        ]
        out = _market_breakdown([make_slip(legs=legs)])
        assert out[0]["market"] == "HighEdge"

    def test_implied_and_avg_odds_computed(self):
        legs = [make_leg(market="1", odds=2.0, status="Won", result_url="https://x.com/a")]
        out = _market_breakdown([make_slip(legs=legs)])[0]
        assert out["implied_win_rate"] == 50.0
        assert out["win_rate"] == 100.0
        assert out["edge"] == 50.0
        assert out["avg_odds"] == 2.0

    def test_zero_leg_slip_per_leg_stake_guard(self):
        slip = make_slip(slip_status="Won", legs=[])
        out = _market_breakdown([slip])
        assert out == []


class TestLeagueBreakdown:
    def test_missing_league_becomes_unknown(self):
        legs = [make_leg(status="Won", league=None)]
        out = _league_breakdown([make_slip(legs=legs)])
        assert out[0]["league"] == "Unknown"

    def test_dedup_and_profit(self):
        url = "https://x.com/1"
        legs = [
            make_leg(market="1", odds=2.0, status="Won", result_url=url, league="La Liga"),
            make_leg(market="1", odds=2.0, status="Won", result_url=url, league="La Liga"),
        ]
        out = _league_breakdown([make_slip(legs=legs, units=2.0)])
        assert out[0]["legs"] == 1
        assert out[0]["won"] == 1
        assert out[0]["net_profit"] == 2.0

    def test_zero_odds_implied_zero(self):
        legs = [make_leg(status="Won", odds=0.0)]
        out = _league_breakdown([make_slip(legs=legs)])
        assert out[0]["implied_win_rate"] == 0.0


class TestSourceMarketCorrelation:
    def _pred_slip(self, **leg_over):
        leg = make_leg(
            market="1",
            market_type="result",
            final_score="2:1",
            predictions=[{"source": "forebet", "home": 2, "away": 1}, {"source": "xgscore", "home": 0, "away": 0}],
            **leg_over,
        )
        return make_slip(legs=[leg])

    def test_matrix_accuracy_computed(self):
        out = _source_market_correlation([self._pred_slip()])
        assert out["sources"] == ["forebet", "xgscore"]
        assert out["markets"] == ["result"]
        assert out["matrix"]["forebet"]["result"] == {"accuracy": 100.0, "total": 1}
        assert out["matrix"]["xgscore"]["result"] == {"accuracy": 0.0, "total": 1}

    def test_legs_without_predictions_skipped(self):
        slip = make_slip(legs=[make_leg(predictions=[], final_score="2:1")])
        assert _source_market_correlation([slip]) == {"sources": [], "markets": [], "matrix": {}}

    def test_legs_without_final_score_skipped(self):
        slip = make_slip(legs=[make_leg(final_score=None)])
        assert _source_market_correlation([slip]) == {"sources": [], "markets": [], "matrix": {}}

    def test_malformed_final_score_skipped(self):
        slip = make_slip(legs=[make_leg(final_score="not:numeric")])
        assert _source_market_correlation([slip]) == {"sources": [], "markets": [], "matrix": {}}


class TestSourceBreakdown:
    def _slip(self, home, away, final="2:1"):
        leg = make_leg(
            market="Over 2.5",
            market_type="over_under_25",
            final_score=final,
            predictions=[{"source": "forebet", "home": home, "away": away}],
        )
        return make_slip(legs=[leg])

    def test_accuracy_and_mae(self):
        out = _source_breakdown([self._slip(2, 1)])
        assert len(out) == 1
        src = out[0]
        assert src["source"] == "forebet"
        assert src["total_predictions"] == 1
        assert src["correct_predictions"] == 1
        assert src["accuracy"] == 100.0
        assert src["score_mae"] == 0.0
        assert src["markets"][0]["accuracy"] == 100.0

    def test_mae_computed_for_wrong_score(self):
        out = _source_breakdown([self._slip(5, 0, final="2:1")])
        assert out[0]["score_mae"] == 2.0
        assert out[0]["accuracy"] == 100.0

    def test_malformed_score_leg_skipped(self):
        slip = self._slip(2, 1)
        slip.legs[0].final_score = "bad"
        assert _source_breakdown([slip]) == []

    def test_missing_predictions_skipped(self):
        slip = make_slip(legs=[make_leg(predictions=[], final_score="2:1")])
        assert _source_breakdown([slip]) == []

    def test_sorted_by_accuracy_desc(self):
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


class TestPnlByMarket:
    def test_dedup_counts_aggregate_profit(self):
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

    def test_sorted_by_abs_net_profit(self):
        legs = [
            make_leg(market="Small", odds=1.5, status="Won", result_url="https://x.com/a"),
            make_leg(market="Big", odds=10.0, status="Lost", result_url="https://x.com/b"),
        ]
        out = _pnl_by_market([make_slip(legs=legs, units=2.0)])
        assert out[0]["market"] == "Big"


class TestProfileScatter:
    def test_scatter_metrics(self):
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

    def test_pending_slips_excluded(self):
        slips = [make_slip(profile="p", slip_status="Pending")]
        assert _profile_scatter(slips) == []

    def test_multiple_profiles_separated(self):
        slips = [
            make_slip(profile="a", slip_status="Won"),
            make_slip(profile="b", slip_status="Lost", slip_id=2),
        ]
        out = _profile_scatter(slips)
        assert {r["profile"] for r in out} == {"a", "b"}


class TestCorrelationMatrix:
    def test_matrix_structure_and_dedup(self):
        url = "https://x.com/1"
        legs = [
            make_leg(market="1", odds=2.0, status="Won", league="La Liga", result_url=url),
            make_leg(market="1", odds=2.0, status="Won", league="La Liga", result_url=url),
            make_leg(market="X", odds=3.0, status="Lost", league="Serie A", result_url="https://x.com/2"),
        ]
        out = _correlation_matrix([make_slip(legs=legs)])
        assert out["leagues"] == ["La Liga", "Serie A"]
        assert out["markets"] == ["1", "X"]
        cell = out["matrix"]["La Liga"]["1"]
        assert cell["total"] == 1
        assert cell["win_rate"] == 100.0
        assert cell["edge"] == 50.0

    def test_zero_odds_implied_zero(self):
        legs = [make_leg(status="Won", odds=0.0)]
        out = _correlation_matrix([make_slip(legs=legs)])
        assert out["matrix"]["La Liga"]["1"]["edge"] == 100.0

    def test_empty_slips(self):
        out = _correlation_matrix([])
        assert out == {"leagues": [], "markets": [], "matrix": {}}
