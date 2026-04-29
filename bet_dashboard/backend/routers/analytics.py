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
    data: dict[str, dict] = {}
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
            data[m]["legs"] += 1
            data[m]["sum_odds"] += leg.odds
            data[m]["sum_implied"] += (1.0 / leg.odds) if leg.odds > 0 else 0.0
            if l_status == "Won":
                data[m]["won"] += 1
                data[m]["net_profit"] += (leg.odds - 1) * per_leg_stake
            else:
                data[m]["lost"] += 1
                data[m]["net_profit"] -= per_leg_stake

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


# ── Existing helpers (unchanged) ───────────────────────────────────────────────


def _pnl_by_market(slips) -> list[dict]:
    data: dict[str, dict] = {}
    for slip in slips:
        status_str = _get_status_value(slip.slip_status)
        if status_str not in ("Won", "Lost"):
            continue
        n_legs = max(len(slip.legs), 1)
        for leg in slip.legs:
            leg_status_str = _get_status_value(leg.status)
            if leg_status_str not in ("Won", "Lost"):
                continue
            m = str(leg.market)
            if m not in data:
                data[m] = {"market": m, "won": 0, "lost": 0, "net_profit": 0.0}
            per_leg_stake = slip.units / n_legs
            if leg_status_str == "Won":
                data[m]["won"] += 1
                data[m]["net_profit"] += (leg.odds - 1) * per_leg_stake
            else:
                data[m]["lost"] += 1
                data[m]["net_profit"] -= per_leg_stake
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

    return {
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
    }
