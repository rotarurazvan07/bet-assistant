"""Property-based tests for core.analytics_utils (issue #61).

Complements test_analytics_helpers.py (example-based delegation tests) with
hypothesis-driven invariants over arbitrary inputs. Every property is
declared with its invariant in the test name (specification style).
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from core.analytics_utils import (
    _get_status_value,
    calculate_biggest_win_loss,
    calculate_correlation_data,
    calculate_daily_summary,
    calculate_kelly_recommendation,
    calculate_market_accuracy,
    calculate_overall_edge,
    calculate_profit_factor,
    calculate_rolling_edge,
    calculate_streak_metrics,
    get_rolling_edge_trend,
)

# ---------------------------------------------------------------------------
# Slip fixtures (pure stand-ins, mirroring BetSlip attributes used by module)
# ---------------------------------------------------------------------------


@dataclass
class LegStub:
    status: str = "Won"
    market: str = "Result"
    result_url: str = ""


@dataclass
class SlipStub:
    slip_status: str = "Won"
    date_generated: str = "2026-09-01"
    total_odds: float = 2.0
    units: float = 1.0
    legs: list = field(default_factory=list)
    profile: str = "medium_risk"


SLIP_STATUSES = ("Won", "Lost", "Pending", "Live")


def _pnl(status: str, total_odds: float, units: float) -> float:
    """Reference net P&L used by several invariants."""
    if status == "Won":
        return (total_odds - 1.0) * units
    return -units


def _settle_seq(seq):
    """Build settled-only SlipStub list from (status, odds, units) tuples."""
    out = []
    for status, odds, units in seq:
        out.append(SlipStub(slip_status=status, total_odds=odds, units=units))
    return out


def _split_profit(seq):
    wins = sum(o * u - u for s, o, u in seq if s == "Won")
    losses = sum(u for s, o, u in seq if s == "Lost")
    return wins, losses


# ---------------------------------------------------------------------------
# Hypothesis strategies (module-level, bounded, deterministic seeds)
# ---------------------------------------------------------------------------

STATUS_STRAT = st.sampled_from(SLIP_STATUSES)
ODDS_STRAT = st.floats(min_value=1.01, max_value=100.0, allow_nan=False, allow_infinity=False)
UNITS_STRAT = st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False)
DATE_STRAT = st.dates(min_value=datetime(2026, 1, 1).date(), max_value=datetime(2026, 12, 31).date())


def _to_status(x):
    return x


def _to_slip(triple):
    if len(triple) == 4:
        status, odds, units, day = triple
        day_str = day.isoformat() if hasattr(day, "isoformat") else day
    else:
        status, odds, units = triple
        day_str = "2026-09-01"
    return SlipStub(slip_status=status, total_odds=odds, units=units, date_generated=day_str)


def _to_legged_slip(pair):
    status, legs = pair
    return SlipStub(slip_status=status, legs=legs)


def _to_leg(pair):
    status, market, url = pair
    return LegStub(status=status, market=market, result_url=url)


DAYS = st.dates(min_value=datetime(2026, 1, 1).date(), max_value=datetime(2026, 9, 24).date())
TRIPLES = st.tuples(STATUS_STRAT, ODDS_STRAT, UNITS_STRAT, DAYS)

SLIPS_STRAT = st.lists(TRIPLES, min_size=0, max_size=12).map(lambda rows: [_to_slip(t) for t in rows])
SETTLED_STRAT = st.lists(
    st.tuples(st.sampled_from(("Won", "Lost")), ODDS_STRAT, UNITS_STRAT, DAYS),
    min_size=0,
    max_size=12,
).map(lambda rows: [_to_slip(t) for t in rows])


PENDING_STRAT = st.lists(
    st.tuples(st.just("Pending"), ODDS_STRAT, UNITS_STRAT), min_size=1, max_size=5
).map(lambda rows: [_to_slip(t) for t in rows])
NOISE_STRAT = st.lists(
    st.tuples(st.sampled_from(("Pending", "Live")), ODDS_STRAT, UNITS_STRAT), min_size=1, max_size=4
).map(lambda rows: [_to_slip(t) for t in rows])
WINS_ONLY_STRAT = st.lists(
    st.tuples(st.just("Won"), ODDS_STRAT, UNITS_STRAT), min_size=1, max_size=5
).map(lambda rows: [_to_slip(t) for t in rows])
LOSSES_ONLY_STRAT = st.lists(
    st.tuples(st.just("Lost"), ODDS_STRAT, UNITS_STRAT), min_size=1, max_size=5
).map(lambda rows: [_to_slip(t) for t in rows])

MARKETS = st.sampled_from(("Result", "Over/Under 2.5", "BTTS", "Double Chance 1X", "Unknown"))
LEG_TRIPLES = st.tuples(STATUS_STRAT, MARKETS, st.text(min_size=1, max_size=8))
LEGS_STRAT = st.lists(LEG_TRIPLES, min_size=0, max_size=6).map(lambda rows: [_to_leg(t) for t in rows])
LEGGED_SLIPS_STRAT = st.lists(st.tuples(STATUS_STRAT, LEGS_STRAT), min_size=0, max_size=6).map(
    lambda rows: [_to_legged_slip(p) for p in rows]
)


# speed: bounded examples, no per-example deadline (flakiness guard per workflow)
COMMON = settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])


# ---------------------------------------------------------------------------
# _get_status_value
# ---------------------------------------------------------------------------


class TestGetStatusValue:
    @given(s=st.sampled_from(SLIP_STATUSES))
    @settings(max_examples=20, deadline=None)
    def test_plain_string_passes_through(self, s):
        assert _get_status_value(s) == s

    @given(s=st.sampled_from(SLIP_STATUSES))
    @settings(max_examples=20, deadline=None)
    def test_enum_member_value_extracted(self, s):
        from enum import Enum

        class S(Enum):
            WON = s

        assert _get_status_value(S.WON) == s


# ---------------------------------------------------------------------------
# calculate_overall_edge
# ---------------------------------------------------------------------------


class TestOverallEdgeProperties:
    @given(slips=SLIPS_STRAT)
    @COMMON
    def test_edge_is_finite_and_ranges_check_for_arbitrary_slips(self, slips):
        edge = calculate_overall_edge(slips)
        assert isinstance(edge, float)
        assert math.isfinite(edge)
        # win_rate and implied both live in [0, 100] -> edge in [-100, 100]
        assert -100.0 <= edge <= 100.0

    @given(seq=SETTLED_STRAT)
    @COMMON
    def test_edge_equals_actual_minus_implied_win_rate(self, seq):
        if not seq:
            assert calculate_overall_edge(seq) == 0.0
            return
        n = len(seq)
        won = len([s for s in seq if s.slip_status == "Won"])
        actual = round(won / n * 100, 2)
        implied = round(sum(1.0 / s.total_odds for s in seq) / n * 100, 2)
        assert calculate_overall_edge(seq) == round(actual - implied, 2)

    @given(pending=PENDING_STRAT)
    @settings(max_examples=15, deadline=None)
    def test_all_unsettled_slips_yield_zero_edge(self, pending):
        assert calculate_overall_edge(pending) == 0.0

    def test_empty_slips_yield_zero_edge(self):
        assert calculate_overall_edge([]) == 0.0


# ---------------------------------------------------------------------------
# calculate_kelly_recommendation
# ---------------------------------------------------------------------------


class TestKellyProperties:
    @given(
        n_won=st.integers(min_value=0, max_value=50),
        n_settled=st.integers(min_value=0, max_value=50),
        avg_odds=st.floats(min_value=1.01, max_value=50.0, allow_nan=False),
        bankroll=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False),
    )
    @COMMON
    def test_suggested_units_bounded_by_zero_and_bankroll(self, n_won, n_settled, avg_odds, bankroll):
        n_won = min(n_won, n_settled)  # domain: cannot win more slips than settled
        units = calculate_kelly_recommendation(n_won, n_settled, avg_odds, bankroll)
        assert isinstance(units, float)
        assert math.isfinite(units)
        # upper bound carries a half-cent tolerance: output is rounded to 2dp and
        # may round up (bankroll=10.006 -> 10.01 when kelly fraction is 1.0)
        assert 0.0 <= units <= max(bankroll, 0.0) + 0.01

    @given(
        n_won=st.integers(min_value=0, max_value=50),
        avg_odds=st.floats(min_value=1.01, max_value=50.0, allow_nan=False),
        bankroll=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False),
    )
    @COMMON
    def test_zero_settled_yields_zero_units(self, n_won, avg_odds, bankroll):
        assert calculate_kelly_recommendation(n_won, 0, avg_odds, bankroll) == 0.0

    @given(
        n_won=st.integers(min_value=0, max_value=20),
        n_settled=st.integers(min_value=1, max_value=20),
        bankroll=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False),
    )
    @COMMON
    def test_odds_at_or_below_one_yields_zero_units(self, n_won, n_settled, bankroll):
        assert calculate_kelly_recommendation(n_won, n_settled, 1.0, bankroll) == 0.0
        assert calculate_kelly_recommendation(n_won, n_settled, 0.5, bankroll) == 0.0

    @given(
        n_won1=st.integers(min_value=0, max_value=30),
        extra_won=st.integers(min_value=1, max_value=10),
        n_settled=st.integers(min_value=1, max_value=40),
        avg_odds=st.floats(min_value=1.1, max_value=10.0, allow_nan=False),
        bankroll=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False),
    )
    @settings(max_examples=25, deadline=None)
    def test_units_monotone_nondecreasing_in_wins(self, n_won1, extra_won, n_settled, avg_odds, bankroll):
        w1 = min(n_won1, n_settled)
        w2 = min(w1 + extra_won, n_settled)
        u1 = calculate_kelly_recommendation(w1, n_settled, avg_odds, bankroll)
        u2 = calculate_kelly_recommendation(w2, n_settled, avg_odds, bankroll)
        assert u2 >= u1 - 1e-9

    @given(
        n_won=st.integers(min_value=0, max_value=30),
        n_settled=st.integers(min_value=1, max_value=40),
        avg_odds=st.floats(min_value=1.01, max_value=20.0, allow_nan=False),
        bankroll=st.floats(min_value=1.0, max_value=1000.0, allow_nan=False),
    )
    @COMMON
    def test_units_match_kelly_formula_rounded(self, n_won, n_settled, avg_odds, bankroll):
        n_won = min(n_won, n_settled)
        p = n_won / n_settled
        b = avg_odds - 1.0
        fraction = (b * p - (1.0 - p)) / b
        expected = round(fraction * bankroll, 2) if fraction > 0 else 0.0
        assert calculate_kelly_recommendation(n_won, n_settled, avg_odds, bankroll) == expected


# ---------------------------------------------------------------------------
# calculate_rolling_edge
# ---------------------------------------------------------------------------


class TestRollingEdgeProperties:
    @given(slips=SLIPS_STRAT)
    @COMMON
    def test_pending_only_or_empty_yield_empty_list(self, slips):
        result = calculate_rolling_edge(slips, window_days=7)
        assert isinstance(result, list)
        if not any(_get_status_value(s.slip_status) in ("Won", "Lost") for s in slips):
            assert result == []

    @given(
        rows=st.lists(
            st.tuples(st.sampled_from(("Won", "Lost")), st.integers(min_value=0, max_value=6)),
            min_size=3,
            max_size=8,
        )
    )
    @settings(max_examples=25, deadline=None)
    def test_single_day_window_with_three_slips_emits_one_point(self, rows):
        base = datetime(2026, 9, 20)
        slips = [
            SlipStub(
                slip_status=status,
                date_generated=(base - timedelta(days=offset)).strftime("%Y-%m-%d"),
                total_odds=2.0,
                units=1.0,
            )
            for status, offset in rows
        ]
        result = calculate_rolling_edge(slips, window_days=7)
        # dates span <=6 days -> the window anchored at the max date sees all slips
        max_date = max(s.date_generated for s in slips)
        point = next((p for p in result if p["date"] == max_date), None)
        assert point is not None
        n = point["sample_size"]
        assert n == len(slips)
        wins = len([s for s in slips if _get_status_value(s.slip_status) == "Won"])
        # odds fixed at 2.0 -> implied per slip is exactly 0.5 -> rolling_implied 50.0
        assert point["rolling_edge"] == round(wins / n * 100 - 50.0, 2)

    @given(window=st.integers(min_value=1, max_value=30))
    @settings(max_examples=20, deadline=None)
    def test_output_points_carry_required_fields(self, window):
        slips = [
            SlipStub(slip_status="Won", date_generated=f"2026-09-1{d}", total_odds=2.0, units=1.0)
            for d in range(5)
        ]
        result = calculate_rolling_edge(slips, window_days=window)
        for point in result:
            assert set(point.keys()) == {"date", "rolling_edge", "rolling_win_rate", "rolling_implied", "sample_size"}
            assert point["sample_size"] >= 3


# ---------------------------------------------------------------------------
# calculate_daily_summary
# ---------------------------------------------------------------------------


def _ref_daily_summary(seq):
    """Mirror of calculate_daily_summary accumulation order (exact FP equality)."""
    settled = [s for s in seq if _get_status_value(s.slip_status) in ("Won", "Lost")]
    settled.sort(key=lambda x: x.date_generated)
    from bet_framework.core.type_defs import Outcome

    daily = {}
    for s in settled:
        day = s.date_generated
        if day not in daily:
            daily[day] = {"slips_count": 0, "units_bet": 0.0, "units_won": 0.0, "won_count": 0}
        stats = daily[day]
        stats["slips_count"] += 1
        stats["units_bet"] += s.units
        if s.slip_status == Outcome.WON:
            stats["units_won"] += s.total_odds * s.units
            stats["won_count"] += 1
    rows = []
    cum_bet = 0.0
    cum_profit = 0.0
    cum_won = 0
    cum_settled = 0
    for day in sorted(daily.keys()):
        stats = daily[day]
        profit = stats["units_won"] - stats["units_bet"]
        cum_bet += stats["units_bet"]
        cum_profit += profit
        cum_won += stats["won_count"]
        cum_settled += stats["slips_count"]
        rows.append(
            {
                "date": day,
                "slips_count": stats["slips_count"],
                "units_bet": round(stats["units_bet"], 2),
                "units_won": round(stats["units_won"], 2),
                "net_profit": round(profit, 2),
                "cumulative_profit": round(cum_profit, 2),
                "cumulative_bet": round(cum_bet, 2),
                "roi_percentage": round((cum_profit / cum_bet * 100) if cum_bet else 0, 2),
                "win_rate": round((cum_won / cum_settled * 100) if cum_settled else 0, 2),
            }
        )
    return rows


class TestDailySummaryProperties:
    @given(seq=SETTLED_STRAT)
    @COMMON
    def test_matches_reference_accumulation_exactly(self, seq):
        assert calculate_daily_summary(seq) == _ref_daily_summary(seq)

    @given(seq=SETTLED_STRAT)
    @COMMON
    def test_rows_sorted_ascending_and_cumulative_monotone(self, seq):
        rows = calculate_daily_summary(seq)
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates)
        prev_cum = -math.inf
        for r in rows:
            assert r["cumulative_bet"] >= prev_cum - 1e-9 or prev_cum == -math.inf
            prev_cum = r["cumulative_bet"]
            assert 0.0 <= r["win_rate"] <= 100.0
            assert -100.0 <= r["roi_percentage"] <= 1e7
            assert math.isfinite(r["net_profit"])

    @given(seq=SETTLED_STRAT)
    @COMMON
    def test_net_profit_identity_won_odds_minus_units(self, seq):
        rows = calculate_daily_summary(seq)
        by_day = {}
        for s in seq:
            day = s.date_generated
            if s.slip_status == "Won":
                by_day[day] = by_day.get(day, 0.0) + (s.total_odds - 1.0) * s.units
            else:
                by_day[day] = by_day.get(day, 0.0) - s.units
        for r in rows:
            expected = round(by_day[r["date"]], 2)
            assert abs(r["net_profit"] - expected) <= 0.02

    def test_empty_slips_yield_empty_summary(self):
        assert calculate_daily_summary([]) == []

    @given(seq=SETTLED_STRAT)
    @COMMON
    def test_profile_and_date_params_do_not_change_output(self, seq):
        """Documented latent trap: profile/date_from/date_to are accepted but ignored.

        AppLogic.daily_summary pre-filters via get_slips before delegating, so the
        chain is functionally correct; this property pins the delegation contract.
        """
        base = calculate_daily_summary(seq)
        filtered = calculate_daily_summary(seq, "low_risk", "2026-01-01", "2026-12-31")
        assert base == filtered


# ---------------------------------------------------------------------------
# calculate_market_accuracy
# ---------------------------------------------------------------------------


class TestMarketAccuracyProperties:
    @given(slips=LEGGED_SLIPS_STRAT)
    @COMMON
    def test_totals_equal_distinct_settled_fingerprints(self, slips):
        results = calculate_market_accuracy(slips)
        expected = {}
        seen = set()
        for slip in slips:
            for leg in slip.legs:
                status = _get_status_value(leg.status)
                if status not in ("Won", "Lost"):
                    continue
                fp = (leg.result_url, leg.market or "Unknown")
                if fp in seen:
                    continue
                seen.add(fp)
                mtype = fp[1]
                bucket = expected.setdefault(mtype, {"won": 0, "lost": 0})
                bucket["won" if status == "Won" else "lost"] += 1
        assert sum(r["total"] for r in results) == len(seen)
        for r in results:
            assert r["won"] + r["lost"] == r["total"]
            assert r["won"] == expected[r["market"]]["won"]
            assert r["lost"] == expected[r["market"]]["lost"]
            assert r["accuracy"] == round(r["won"] / r["total"] * 100, 2)
            assert 0.0 <= r["accuracy"] <= 100.0

    @given(slips=LEGGED_SLIPS_STRAT)
    @COMMON
    def test_sorted_by_total_desc_and_finite(self, slips):
        results = calculate_market_accuracy(slips)
        totals = [r["total"] for r in results]
        assert totals == sorted(totals, reverse=True)
        for r in results:
            assert all(math.isfinite(r[k]) for k in ("accuracy",))

    def test_empty_slips_yield_empty_markets(self):
        assert calculate_market_accuracy([]) == []

    @given(
        statuses=st.lists(STATUS_STRAT, min_size=1, max_size=6),
        url=st.text(min_size=1, max_size=8),
    )
    @settings(max_examples=20, deadline=None)
    def test_duplicate_fingerprint_counted_once(self, statuses, url):
        slip = SlipStub(
            slip_status="Won",
            legs=[LegStub(status=s, market="Result", result_url=url) for s in statuses],
        )
        results = calculate_market_accuracy([slip])
        settled_statuses = [s for s in statuses if s in ("Won", "Lost")]
        if not settled_statuses:
            assert results == []
            return
        assert len(results) == 1
        # every leg shares one fingerprint -> only the first leg counts
        first = settled_statuses[0]
        assert results[0]["total"] == 1
        assert results[0]["won"] == (1 if first == "Won" else 0)


# ---------------------------------------------------------------------------
# calculate_correlation_data
# ---------------------------------------------------------------------------


class TestCorrelationDataProperties:
    @given(seq=SETTLED_STRAT)
    @COMMON
    def test_profit_identity_per_settled_slip(self, seq):
        rows = calculate_correlation_data(seq)
        assert len(rows) == len(seq)
        for slip, row in zip(seq, rows, strict=True):
            expected_profit = round(
                (slip.total_odds * slip.units - slip.units) if slip.slip_status == "Won" else -slip.units,
                2,
            )
            assert row["profit"] == expected_profit
            assert row["status"] == slip.slip_status
            assert row["legs_count"] == 0
            assert row["total_odds"] == round(slip.total_odds, 2)
            assert row["units"] == slip.units

    @given(pending=PENDING_STRAT)
    @settings(max_examples=15, deadline=None)
    def test_unsettled_slips_excluded(self, pending):
        assert calculate_correlation_data(pending) == []

    def test_empty_slips_yield_empty_rows(self):
        assert calculate_correlation_data([]) == []


# ---------------------------------------------------------------------------
# calculate_streak_metrics
# ---------------------------------------------------------------------------


STREAK_BASE = datetime(2026, 1, 10)


def _day_slip(day_offset: int, profit: int):
    """One settled slip whose P&L equals `profit` exactly (integer-safe FP)."""
    day = (STREAK_BASE + timedelta(days=day_offset)).strftime("%Y-%m-%d")
    if profit >= 0:
        return SlipStub(slip_status="Won", date_generated=day, total_odds=profit + 1.0, units=1.0)
    return SlipStub(slip_status="Lost", date_generated=day, total_odds=2.0, units=float(-profit))


def _ref_current_streak(pnl_by_day: dict) -> int:
    """Newest-first walk mirroring calculate_streak_metrics current-stretch logic."""
    current = 0
    ctype = None
    for day in sorted(pnl_by_day.keys(), reverse=True):
        pnl = pnl_by_day[day]
        if pnl == 0:
            continue
        day_type = "win" if pnl > 0 else "loss"
        if ctype is None:
            ctype = day_type
            current = 1
        elif day_type == ctype:
            current += 1
        else:
            break
    if ctype == "loss":
        return -current
    return current if ctype else 0


def _ref_longest_streaks(pnl_by_day: dict) -> tuple:
    """Chronological walk mirroring calculate_streak_metrics longest-run logic."""
    longest_win = 0
    longest_loss = 0
    win_run = 0
    loss_run = 0
    for day in sorted(pnl_by_day.keys()):
        pnl = pnl_by_day[day]
        if pnl == 0:
            continue
        if pnl > 0:
            win_run += 1
            loss_run = 0
            longest_win = max(longest_win, win_run)
        else:
            loss_run += 1
            win_run = 0
            longest_loss = max(longest_loss, loss_run)
    return longest_win, longest_loss


def _ref_streak_metrics(profits_by_day: dict) -> dict:
    """Mirror of calculate_streak_metrics over {date_str: pnl} map (exact walk)."""
    if not profits_by_day:
        return {"current_streak": 0, "longest_win_streak": 0, "longest_loss_streak": 0}
    longest_win, longest_loss = _ref_longest_streaks(profits_by_day)
    return {
        "current_streak": _ref_current_streak(profits_by_day),
        "longest_win_streak": longest_win,
        "longest_loss_streak": longest_loss,
    }


class TestStreakMetricsProperties:
    @given(
        pairs=st.lists(
            st.tuples(st.integers(min_value=0, max_value=25), st.integers(min_value=-3, max_value=3)),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=30, deadline=None)
    def test_matches_reference_walk_exactly(self, pairs):
        seq = [_day_slip(d, p) for d, p in pairs]
        by_day = {}
        for d, p in pairs:
            day = (STREAK_BASE + timedelta(days=d)).strftime("%Y-%m-%d")
            by_day[day] = by_day.get(day, 0.0) + float(p)
        assert calculate_streak_metrics(seq) == _ref_streak_metrics(by_day)

    @given(
        pairs=st.lists(
            st.tuples(st.integers(min_value=0, max_value=25), st.integers(min_value=-3, max_value=3)),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=30, deadline=None)
    def test_streak_bounds_and_sign_invariants(self, pairs):
        seq = [_day_slip(d, p) for d, p in pairs]
        metrics = calculate_streak_metrics(seq)
        n_nonzero = len([p for _, p in pairs if p != 0])
        assert abs(metrics["current_streak"]) <= n_nonzero
        assert metrics["longest_win_streak"] <= n_nonzero
        assert metrics["longest_loss_streak"] <= n_nonzero
        assert metrics["longest_win_streak"] >= 0
        assert metrics["longest_loss_streak"] >= 0
        if metrics["current_streak"] > 0:
            assert metrics["longest_win_streak"] >= metrics["current_streak"]
        elif metrics["current_streak"] < 0:
            assert metrics["longest_loss_streak"] >= abs(metrics["current_streak"])

    def test_empty_slips_yield_zero_streaks(self):
        assert calculate_streak_metrics([]) == {
            "current_streak": 0,
            "longest_win_streak": 0,
            "longest_loss_streak": 0,
        }

    @given(pending=PENDING_STRAT)
    @settings(max_examples=15, deadline=None)
    def test_unsettled_only_slips_yield_zero_streaks(self, pending):
        assert calculate_streak_metrics(pending) == {
            "current_streak": 0,
            "longest_win_streak": 0,
            "longest_loss_streak": 0,
        }

    def test_breakeven_days_neither_count_nor_break_streaks(self):
        # win day, break-even day, win day -> 2-day win streak; zero day skipped everywhere
        seq = [_day_slip(0, 2), _day_slip(1, 0), _day_slip(2, 1)]
        metrics = calculate_streak_metrics(seq)
        assert metrics["current_streak"] == 2
        assert metrics["longest_win_streak"] == 2
        assert metrics["longest_loss_streak"] == 0

    def test_streak_breaks_at_sign_change(self):
        # offsets grow toward today: newest day (offset 2) is the loss after two wins
        seq = [_day_slip(0, 1), _day_slip(1, 2), _day_slip(2, -1)]
        metrics = calculate_streak_metrics(seq)
        assert metrics["current_streak"] == -1
        assert metrics["longest_win_streak"] == 2
        assert metrics["longest_loss_streak"] == 1

    def test_all_breakeven_days_yield_zero_current_streak(self):
        seq = [_day_slip(0, 0), _day_slip(1, 0)]
        assert calculate_streak_metrics(seq) == {
            "current_streak": 0,
            "longest_win_streak": 0,
            "longest_loss_streak": 0,
        }

    def test_multi_slip_day_aggregates_pnl(self):
        # two slips on one day: net +1 -> winning day; single losing day after
        day_win = (STREAK_BASE + timedelta(days=1)).strftime("%Y-%m-%d")
        day_loss = STREAK_BASE.strftime("%Y-%m-%d")
        seq = [
            SlipStub(slip_status="Won", date_generated=day_win, total_odds=3.0, units=1.0),
            SlipStub(slip_status="Lost", date_generated=day_win, total_odds=2.0, units=1.0),
            SlipStub(slip_status="Lost", date_generated=day_loss, total_odds=2.0, units=2.0),
        ]
        metrics = calculate_streak_metrics(seq)
        assert metrics["current_streak"] == 1  # newest day nets +2-1 = +1 -> win
        assert metrics["longest_win_streak"] == 1
        assert metrics["longest_loss_streak"] == 1


# ---------------------------------------------------------------------------
# calculate_profit_factor
# ---------------------------------------------------------------------------


class TestProfitFactorProperties:
    @given(seq=SETTLED_STRAT)
    @COMMON
    def test_matches_reference_ratio_exactly(self, seq):
        wins, losses = _split_profit([(s.slip_status, s.total_odds, s.units) for s in seq])
        expected = round(wins / losses, 2) if losses > 0 else 0.0
        assert calculate_profit_factor(seq) == expected

    @given(seq=SETTLED_STRAT)
    @COMMON
    def test_profit_factor_non_negative_and_finite(self, seq):
        pf = calculate_profit_factor(seq)
        assert isinstance(pf, float)
        assert math.isfinite(pf)
        assert pf >= 0.0

    def test_empty_slips_yield_zero_pf(self):
        assert calculate_profit_factor([]) == 0.0

    @given(wins=WINS_ONLY_STRAT)
    @settings(max_examples=15, deadline=None)
    def test_wins_without_losses_yield_zero_pf(self, wins):
        # documented semantics: 0.0 when no losses (not infinity)
        assert calculate_profit_factor(wins) == 0.0

    @given(losses=LOSSES_ONLY_STRAT)
    @settings(max_examples=15, deadline=None)
    def test_losses_without_wins_yield_zero_pf(self, losses):
        assert calculate_profit_factor(losses) == 0.0

    @given(
        settled=SETTLED_STRAT,
        noise=NOISE_STRAT,
    )
    @settings(max_examples=20, deadline=None)
    def test_unsettled_slips_do_not_affect_pf(self, settled, noise):
        assert calculate_profit_factor(settled + noise) == calculate_profit_factor(settled)


# ---------------------------------------------------------------------------
# calculate_biggest_win_loss
# ---------------------------------------------------------------------------


class TestBiggestWinLossProperties:
    @given(seq=SETTLED_STRAT)
    @COMMON
    def test_matches_reference_extremes_exactly(self, seq):
        win_profits = [s.total_odds * s.units - s.units for s in seq if s.slip_status == "Won"]
        loss_profits = [-s.units for s in seq if s.slip_status == "Lost"]
        result = calculate_biggest_win_loss(seq)
        assert result["biggest_win_units"] == (round(max(win_profits), 2) if win_profits else None)
        assert result["biggest_loss_units"] == (round(min(loss_profits), 2) if loss_profits else None)

    @given(seq=SETTLED_STRAT)
    @COMMON
    def test_extremes_bound_every_slip_pnl(self, seq):
        result = calculate_biggest_win_loss(seq)
        for s in seq:
            if s.slip_status == "Won":
                assert result["biggest_win_units"] >= round(s.total_odds * s.units - s.units, 2) - 0.01
            else:
                assert result["biggest_loss_units"] <= round(-s.units, 2) + 0.01

    def test_empty_slips_yield_none_extremes(self):
        assert calculate_biggest_win_loss([]) == {"biggest_win_units": None, "biggest_loss_units": None}

    @given(wins=WINS_ONLY_STRAT)
    @settings(max_examples=15, deadline=None)
    def test_wins_without_losses_yield_none_loss(self, wins):
        result = calculate_biggest_win_loss(wins)
        assert result["biggest_win_units"] is not None
        assert result["biggest_loss_units"] is None

    @given(losses=LOSSES_ONLY_STRAT)
    @settings(max_examples=15, deadline=None)
    def test_losses_without_wins_yield_none_win(self, losses):
        result = calculate_biggest_win_loss(losses)
        assert result["biggest_win_units"] is None
        assert result["biggest_loss_units"] is not None

    @given(
        settled=SETTLED_STRAT,
        noise=NOISE_STRAT,
    )
    @settings(max_examples=20, deadline=None)
    def test_unsettled_slips_do_not_affect_extremes(self, settled, noise):
        assert calculate_biggest_win_loss(settled + noise) == calculate_biggest_win_loss(settled)

    @given(seq=SETTLED_STRAT)
    @COMMON
    def test_consistent_with_correlation_data_profits(self, seq):
        rows = calculate_correlation_data(seq)
        result = calculate_biggest_win_loss(seq)
        win_profits = [r["profit"] for r in rows if r["status"] == "Won"]
        loss_profits = [r["profit"] for r in rows if r["status"] == "Lost"]
        assert result["biggest_win_units"] == (round(max(win_profits), 2) if win_profits else None)
        assert result["biggest_loss_units"] == (round(min(loss_profits), 2) if loss_profits else None)


# ---------------------------------------------------------------------------
# get_rolling_edge_trend
# ---------------------------------------------------------------------------


def _trend_slip(day_offset: int, status: str, odds: float = 2.0, units: float = 1.0):
    day = (datetime.now() - timedelta(days=day_offset)).strftime("%Y-%m-%d")
    return SlipStub(slip_status=status, date_generated=day, total_odds=odds, units=units)


def _ref_trend(seq):
    """Mirror of get_rolling_edge_trend over settled slips (safe offsets only)."""
    today = datetime.now()
    fourteen_days_ago = today - timedelta(days=14)
    recent = [s for s in seq if datetime.strptime(s.date_generated[:10], "%Y-%m-%d") >= fourteen_days_ago]
    if not recent:
        return {"trend": "neutral", "value": 0.0}
    seven_days_ago = today - timedelta(days=7)
    week_1 = [s for s in recent if datetime.strptime(s.date_generated[:10], "%Y-%m-%d") < seven_days_ago]
    week_2 = [s for s in recent if datetime.strptime(s.date_generated[:10], "%Y-%m-%d") >= seven_days_ago]
    diff = calculate_overall_edge(week_2) - calculate_overall_edge(week_1)
    if diff > 0.02:
        trend = "growing"
    elif diff < -0.02:
        trend = "declining"
    else:
        trend = "stable"
    return {"trend": trend, "value": round(calculate_overall_edge(week_2), 2)}


class TestRollingEdgeTrendProperties:
    @given(
        week1_n=st.integers(min_value=0, max_value=4),
        week2_n=st.integers(min_value=0, max_value=4),
        seed=st.integers(min_value=0, max_value=2**16 - 1),
    )
    @settings(max_examples=25, deadline=None)
    def test_matches_reference_trend_exactly(self, week1_n, week2_n, seed):
        import random

        rng = random.Random(seed)
        week1 = [_trend_slip(rng.randint(8, 13), rng.choice(("Won", "Lost"))) for _ in range(week1_n)]
        week2 = [_trend_slip(rng.randint(0, 6), rng.choice(("Won", "Lost"))) for _ in range(week2_n)]
        seq = week1 + week2
        assert get_rolling_edge_trend(seq) == _ref_trend(seq)

    def test_no_recent_slips_yield_neutral_zero(self):
        old_day = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        old = SlipStub(slip_status="Won", date_generated=old_day, total_odds=2.0, units=1.0)
        assert get_rolling_edge_trend([old]) == {"trend": "neutral", "value": 0.0}

    def test_empty_slips_yield_neutral_zero(self):
        assert get_rolling_edge_trend([]) == {"trend": "neutral", "value": 0.0}

    def test_growing_trend_when_recent_week_improves(self):
        # week_1: all Lost @2.0 -> edge -50; week_2: all Won @2.0 -> edge +50
        seq = [_trend_slip(10, "Lost"), _trend_slip(12, "Lost"), _trend_slip(2, "Won"), _trend_slip(4, "Won")]
        result = get_rolling_edge_trend(seq)
        assert result["trend"] == "growing"
        assert result["value"] == 50.0

    def test_declining_trend_when_recent_week_worsens(self):
        seq = [_trend_slip(10, "Won"), _trend_slip(12, "Won"), _trend_slip(2, "Lost"), _trend_slip(4, "Lost")]
        result = get_rolling_edge_trend(seq)
        assert result["trend"] == "declining"
        assert result["value"] == -50.0

    def test_stable_trend_when_edges_equal(self):
        seq = [_trend_slip(9, "Won"), _trend_slip(9, "Lost"), _trend_slip(2, "Won"), _trend_slip(2, "Lost")]
        result = get_rolling_edge_trend(seq)
        assert result["trend"] == "stable"
        assert result["value"] == 0.0
