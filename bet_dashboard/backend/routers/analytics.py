from __future__ import annotations

# Import analytics utilities
from core.analytics_utils import (
    _get_status_value,
    calculate_correlation_data,
    calculate_daily_summary,
    calculate_market_accuracy,
    calculate_rolling_edge,
)
from fastapi import APIRouter, Request
from utils.json_utils import sanitize_floats
from utils.profile_utils import get_profile_params

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _get(request: Request):
    return request.app.state.app_logic


def _get_status_value(status) -> str:
    if hasattr(status, "value"):
        return status.value
    return str(status)


# ── Drawdown ───────────────────────────────────────────────────────────────────


def _drawdown_data(history: list[dict]) -> list[dict]:
    if not history:
        return []
    peak = 0.0
    result = []
    for day in history:
        cum = day["cumulative_profit"]
        if cum > peak:
            peak = cum
        result.append(
            {
                "date": day["date"],
                "drawdown": round(cum - peak, 2),
                "peak": round(peak, 2),
                "cumulative_profit": cum,
            }
        )
    return result


# ── Market breakdown (with per-leg implied win rate) ───────────────────────────


def _market_breakdown(slips) -> list[dict]:
    # data: market -> { "market": str, "unique_legs": set, "won": 0, "lost": 0, "sum_odds": 0.0, "sum_implied": 0.0, "net_profit": 0.0 }
    data: dict[str, dict] = {}

    # Track unique legs to count them only once for win/loss but aggregate profit
    # fingerprint: (result_url, market)
    processed_legs = set()

    for slip in slips:
        s_status = _get_status_value(slip.slip_status)
        if s_status not in ("Won", "Lost"):
            continue
        n_legs = max(len(slip.legs), 1)
        per_leg_stake = slip.units / n_legs

        for leg in slip.legs:
            l_status = _get_status_value(leg.status)
            if l_status not in ("Won", "Lost"):
                continue

            m = str(leg.market)
            if m not in data:
                data[m] = {"market": m, "legs": 0, "won": 0, "lost": 0, "sum_odds": 0.0, "sum_implied": 0.0, "net_profit": 0.0}

            # Always aggregate profit (money is real even if leg is duplicated)
            if l_status == "Won":
                data[m]["net_profit"] += (leg.odds - 1) * per_leg_stake
            else:
                data[m]["net_profit"] -= per_leg_stake

            # Only count win/loss and odds once per unique prediction
            fingerprint = (leg.result_url, m)
            if fingerprint not in processed_legs:
                processed_legs.add(fingerprint)
                data[m]["legs"] += 1
                data[m]["sum_odds"] += leg.odds
                data[m]["sum_implied"] += (1.0 / leg.odds) if leg.odds > 0 else 0.0
                if l_status == "Won":
                    data[m]["won"] += 1
                else:
                    data[m]["lost"] += 1

    result = []
    for m, d in data.items():
        total = d["legs"]
        win_rate = round(d["won"] / total * 100, 1) if total else 0.0
        implied = round(d["sum_implied"] / total * 100, 1) if total else 0.0
        result.append(
            {
                "market": m,
                "legs": total,
                "won": d["won"],
                "lost": d["lost"],
                "win_rate": win_rate,
                "implied_win_rate": implied,
                "edge": round(win_rate - implied, 1),
                "avg_odds": round(d["sum_odds"] / total, 2) if total else 0.0,
                "net_profit": round(d["net_profit"], 2),
            }
        )
    return sorted(result, key=lambda x: x["edge"], reverse=True)


# ── League breakdown (same pattern as market) ──────────────────────────────────


def _league_breakdown(slips) -> list[dict]:
    data: dict[str, dict] = {}
    processed_legs = set()

    for slip in slips:
        s_status = _get_status_value(slip.slip_status)
        if s_status not in ("Won", "Lost"):
            continue
        n_legs = max(len(slip.legs), 1)
        per_leg_stake = slip.units / n_legs

        for leg in slip.legs:
            l_status = _get_status_value(leg.status)
            if l_status not in ("Won", "Lost"):
                continue

            lg = getattr(leg, "league", None) or "Unknown"
            if lg not in data:
                data[lg] = {
                    "league": lg,
                    "legs": 0,
                    "won": 0,
                    "lost": 0,
                    "sum_odds": 0.0,
                    "sum_implied": 0.0,
                    "net_profit": 0.0,
                }

            # Always aggregate profit
            if l_status == "Won":
                data[lg]["net_profit"] += (leg.odds - 1) * per_leg_stake
            else:
                data[lg]["net_profit"] -= per_leg_stake

            # Only count win/loss and odds once per unique prediction
            fingerprint = (leg.result_url, leg.market)
            if fingerprint not in processed_legs:
                processed_legs.add(fingerprint)
                data[lg]["legs"] += 1
                data[lg]["sum_odds"] += leg.odds
                data[lg]["sum_implied"] += (1.0 / leg.odds) if leg.odds > 0 else 0.0
                if l_status == "Won":
                    data[lg]["won"] += 1
                else:
                    data[lg]["lost"] += 1

    result = []
    for lg, d in data.items():
        total = d["legs"]
        win_rate = round(d["won"] / total * 100, 1) if total else 0.0
        implied = round(d["sum_implied"] / total * 100, 1) if total else 0.0
        result.append(
            {
                "league": lg,
                "legs": total,
                "won": d["won"],
                "lost": d["lost"],
                "win_rate": win_rate,
                "implied_win_rate": implied,
                "edge": round(win_rate - implied, 1),
                "avg_odds": round(d["sum_odds"] / total, 2) if total else 0.0,
                "net_profit": round(d["net_profit"], 2),
            }
        )
    return sorted(result, key=lambda x: x["edge"], reverse=True)


# ── Source Reliability Breakdown ────────────────────────────────────────────────


def _predict_outcome_from_score(home_goals: int, away_goals: int, market_label: str, market_type: str) -> str:
    """Predict outcome for a market based on a score prediction."""
    total_goals = home_goals + away_goals

    if market_type == "result":
        if home_goals > away_goals:
            return "HOME"
        elif home_goals == away_goals:
            return "DRAW"
        else:
            return "AWAY"
    elif market_type == "over_under_25":
        return "OVER_25" if total_goals > 2.5 else "UNDER_25"
    elif market_type == "over_under_15":
        return "OVER_15" if total_goals > 1.5 else "UNDER_15"
    elif market_type == "over_under_05":
        return "OVER_05" if total_goals > 0.5 else "UNDER_05"
    elif market_type == "over_under_35":
        return "OVER_35" if total_goals > 3.5 else "UNDER_35"
    elif market_type == "over_under_45":
        return "OVER_45" if total_goals > 4.5 else "UNDER_45"
    elif market_type == "btts":
        return "BTTS_YES" if home_goals > 0 and away_goals > 0 else "BTTS_NO"
    elif market_type == "double_chance":
        if home_goals > away_goals:
            return "DC_1X"
        elif home_goals == away_goals:
            return "DC_X2"
        else:
            return "DC_12"

    return "UNKNOWN"


def _source_breakdown(slips) -> list[dict]:
    """
    Analyze source reliability by looking at per-leg predictions.

    For each source, track:
    - Total predictions made
    - Correct predictions (computed from final_score)
    - Accuracy rate
    - Markets they predict well/poorly
    - Mean Absolute Error (MAE) for score predictions
    """
    source_data: dict[str, dict] = {}

    for slip in slips:
        s_status = _get_status_value(slip.slip_status)
        if s_status not in ("Won", "Lost"):
            continue

        for leg in slip.legs:
            l_status = _get_status_value(leg.status)
            if l_status not in ("Won", "Lost"):
                continue

            # Get predictions for this leg
            predictions = getattr(leg, "predictions", None)
            if not predictions:
                continue

            # Get final score for this leg
            final_score = getattr(leg, "final_score", None)
            if not final_score:
                continue  # Skip legs without final score

            try:
                actual_home, actual_away = map(int, final_score.split(":"))
            except (ValueError, AttributeError):
                continue

            # Determine actual outcome for this leg's market
            market_label = str(leg.market)
            market_type = str(leg.market_type)
            actual_outcome = _predict_outcome_from_score(actual_home, actual_away, market_label, market_type)

            for pred in predictions:
                source = pred.get("source", "unknown")
                pred_home = pred.get("home", 0)
                pred_away = pred.get("away", 0)

                if source not in source_data:
                    source_data[source] = {
                        "source": source,
                        "total_predictions": 0,
                        "correct_predictions": 0,
                        "markets": {},
                        "score_mae_sum": 0.0,  # Sum of |pred_home - actual_home| + |pred_away - actual_away|
                    }

                source_data[source]["total_predictions"] += 1

                # Compute predicted outcome for this market from source's predicted score
                predicted_outcome = _predict_outcome_from_score(pred_home, pred_away, market_label, market_type)

                # Check if prediction was correct
                is_correct = predicted_outcome == actual_outcome

                if is_correct:
                    source_data[source]["correct_predictions"] += 1

                # Track score MAE
                source_data[source]["score_mae_sum"] += abs(pred_home - actual_home) + abs(pred_away - actual_away)

                # Track per-market performance
                if market_label not in source_data[source]["markets"]:
                    source_data[source]["markets"][market_label] = {"total": 0, "correct": 0}
                source_data[source]["markets"][market_label]["total"] += 1
                if is_correct:
                    source_data[source]["markets"][market_label]["correct"] += 1

    result = []
    for source, data in source_data.items():
        total = data["total_predictions"]
        correct = data["correct_predictions"]
        accuracy = round(correct / total * 100, 1) if total else 0.0
        score_mae = round(data["score_mae_sum"] / (total * 2), 2) if total else 0.0  # Avg goals error per team

        # Per-market breakdown
        market_breakdown = []
        for mkt, mkt_data in data["markets"].items():
            mkt_total = mkt_data["total"]
            mkt_correct = mkt_data["correct"]
            market_breakdown.append(
                {
                    "market": mkt,
                    "predictions": mkt_total,
                    "correct": mkt_correct,
                    "accuracy": round(mkt_correct / mkt_total * 100, 1) if mkt_total else 0.0,
                }
            )

        result.append(
            {
                "source": source,
                "total_predictions": total,
                "correct_predictions": correct,
                "accuracy": accuracy,
                "score_mae": score_mae,
                "markets": sorted(market_breakdown, key=lambda x: x["accuracy"], reverse=True),
            }
        )

    return sorted(result, key=lambda x: x["accuracy"], reverse=True)


# ── Existing helpers (unchanged) ───────────────────────────────────────────────


def _pnl_by_market(slips) -> list[dict]:
    data: dict[str, dict] = {}
    processed_legs = set()

    for slip in slips:
        status_str = _get_status_value(slip.slip_status)
        if status_str not in ("Won", "Lost"):
            continue
        n_legs = max(len(slip.legs), 1)
        per_leg_stake = slip.units / n_legs

        for leg in slip.legs:
            leg_status_str = _get_status_value(leg.status)
            if leg_status_str not in ("Won", "Lost"):
                continue

            m = str(leg.market)
            if m not in data:
                data[m] = {"market": m, "won": 0, "lost": 0, "net_profit": 0.0}

            # PnL should always aggregate because money is real even for duplicates
            if leg_status_str == "Won":
                data[m]["net_profit"] += (leg.odds - 1) * per_leg_stake
            else:
                data[m]["net_profit"] -= per_leg_stake

            # Deduplicate counts for "Market Intelligence" truth
            fingerprint = (leg.result_url, m)
            if fingerprint not in processed_legs:
                processed_legs.add(fingerprint)
                if leg_status_str == "Won":
                    data[m]["won"] += 1
                else:
                    data[m]["lost"] += 1

    return sorted(
        (dict(v, net_profit=round(v["net_profit"], 2)) for v in data.values()),
        key=lambda x: abs(x["net_profit"]),
        reverse=True,
    )


def _profile_scatter(slips) -> list[dict]:
    profiles: dict[str, dict] = {}
    for slip in slips:
        status_str = _get_status_value(slip.slip_status)
        if status_str not in ("Won", "Lost"):
            continue
        p = slip.profile
        if p not in profiles:
            profiles[p] = {"profile": p, "total": 0, "won": 0, "sum_odds": 0.0, "sum_profit": 0.0}
        profiles[p]["total"] += 1
        profiles[p]["sum_odds"] += slip.total_odds
        if status_str == "Won":
            profiles[p]["won"] += 1
            profiles[p]["sum_profit"] += (slip.total_odds - 1) * slip.units
        else:
            profiles[p]["sum_profit"] -= slip.units
    return [
        {
            "profile": p,
            "avg_odds": round(d["sum_odds"] / d["total"], 2),
            "win_rate": round((d["won"] / d["total"]) * 100, 1),
            "net_profit": round(d["sum_profit"], 2),
            "volume": d["total"],
            "break_even_win_rate": round(d["total"] / d["sum_odds"] * 100, 1) if d["sum_odds"] > 0 else 0.0,
        }
        for p, d in profiles.items()
    ]


# ── Main endpoint ──────────────────────────────────────────────────────────────


@router.get("")
def get_analytics(
    request: Request,
    profiles: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    logic = _get(request).logic

    if profiles is None:
        profiles_param = get_profile_params(request)
        if profiles_param:
            profiles = profiles_param

    prof = profiles if profiles and len(profiles) > 0 else None
    df_ = date_from or None
    dt_ = date_to or None

    slips = logic.get_slips(prof, df_, dt_)
    all_slips = logic.get_slips(None, df_, dt_)

    # Get slips for daily summary calculation
    daily_summary_slips = logic.get_slips(prof or "all", df_, dt_)

    response_data = {
        "history": calculate_daily_summary(daily_summary_slips, prof, df_, dt_),
        "market_accuracy": calculate_market_accuracy(daily_summary_slips),
        "pnl_by_market": _pnl_by_market(slips),
        "correlation": calculate_correlation_data(daily_summary_slips),
        "profile_scatter": _profile_scatter(slips),
        "stats": logic.stats(prof, df_, dt_),
        "profiles": sorted({slip.profile for slip in all_slips}),
        # ── Phase 1 additions ──────────────────────────────────────────
        "rolling_edge": calculate_rolling_edge(slips, 14),
        "drawdown": _drawdown_data(calculate_daily_summary(daily_summary_slips, prof, df_, dt_)),
        "market_breakdown": _market_breakdown(slips),
        "league_breakdown": _league_breakdown(slips),
        "correlation_matrix": _correlation_matrix(slips),
        # ── Source Reliability ─────────────────────────────────────────
        "source_breakdown": _source_breakdown(slips),
    }
    return sanitize_floats(response_data)


def _correlation_matrix(slips) -> dict:
    # Matrix of (League, Market) stats
    data = {}
    leagues = set()
    markets = set()
    processed_legs = set()

    for slip in slips:
        s_status = _get_status_value(slip.slip_status)
        if s_status not in ("Won", "Lost"):
            continue

        for leg in slip.legs:
            l_status = _get_status_value(leg.status)
            if l_status not in ("Won", "Lost"):
                continue

            m = str(leg.market)
            lg = getattr(leg, "league", None) or "Unknown"

            fingerprint = (leg.result_url, m)
            if fingerprint in processed_legs:
                continue
            processed_legs.add(fingerprint)

            leagues.add(lg)
            markets.add(m)

            if lg not in data:
                data[lg] = {}
            if m not in data[lg]:
                data[lg][m] = {"won": 0, "total": 0, "sum_implied": 0.0}

            data[lg][m]["total"] += 1
            data[lg][m]["sum_implied"] += (1.0 / leg.odds) if leg.odds > 0 else 0.0
            if l_status == "Won":
                data[lg][m]["won"] += 1

    # Finalize matrix
    matrix = {}
    for lg in data:
        matrix[lg] = {}
        for m in data[lg]:
            d = data[lg][m]
            wr = round(d["won"] / d["total"] * 100, 1)
            implied = round(d["sum_implied"] / d["total"] * 100, 1)
            matrix[lg][m] = {"win_rate": wr, "edge": round(wr - implied, 1), "total": d["total"]}

    return {"leagues": sorted(leagues), "markets": sorted(markets), "matrix": matrix}
