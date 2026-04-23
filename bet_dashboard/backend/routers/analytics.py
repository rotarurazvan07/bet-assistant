from __future__ import annotations

from fastapi import APIRouter, Request

from utils.profile_utils import get_profile_params

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _get(request: Request):
    return request.app.state.app_logic


def _get_status_value(status) -> str:
    """Get the string value from an enum or string status."""
    if hasattr(status, "value"):
        return status.value
    return str(status)


def _odds_distribution(slips) -> list[dict]:
    buckets = [
        (1.00, 1.50, "1.0–1.5"),
        (1.50, 2.00, "1.5–2.0"),
        (2.00, 3.00, "2.0–3.0"),
        (3.00, 5.00, "3.0–5.0"),
        (5.00, 10.0, "5.0–10.0"),
        (10.0, 999, "10.0+"),
    ]
    settled = [s for s in slips if _get_status_value(s.slip_status) in ("Won", "Lost")]
    result = []
    for lo, hi, label in buckets:
        batch = [s for s in settled if lo <= s.total_odds < hi]
        if not batch:
            continue
        wins = sum(1 for s in batch if _get_status_value(s.slip_status) == "Won")
        result.append(
            {
                "range": label,
                "count": len(batch),
                "wins": wins,
                "losses": len(batch) - wins,
                "win_rate": round((wins / len(batch)) * 100, 1),
            }
        )
    return result


def _pnl_by_market(slips) -> list[dict]:
    """Net profit contribution per market label from settled legs."""
    data: dict[str, dict] = {}
    settled_count = 0
    for slip in slips:
        status_str = _get_status_value(slip.slip_status)
        if status_str not in ("Won", "Lost"):
            continue
        settled_count += 1
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
    """Per-profile summary: avg odds, win rate, volume — for scatter chart."""
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
        }
        for p, d in profiles.items()
    ]


@router.get("")
def get_analytics(
    request: Request,
    profiles: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    logic = _get(request).logic

    # Handle both 'profiles' and 'profiles[]' query parameter names
    # FastAPI's 'profiles' parameter only catches 'profiles', not 'profiles[]'
    if profiles is None:
        # Try to get from 'profiles[]' if 'profiles' was not provided
        profiles_param = get_profile_params(request)
        if profiles_param:
            profiles = profiles_param

    # Normalize: empty list or None means all profiles (pass None to backend)
    prof = profiles if profiles and len(profiles) > 0 else None

    df_ = date_from or None
    dt_ = date_to or None

    history = logic.daily_summary(prof, df_, dt_)

    slips = logic.get_slips(prof, df_, dt_)
    all_slips = logic.get_slips(None, df_, dt_)

    # Debug logging
    print(f"[Analytics] profiles={profiles}, prof={prof}, date_from={df_}, date_to={dt_}")
    print(f"[Analytics] slips count: {len(slips)}, all_slips count: {len(all_slips)}")

    pnl = _pnl_by_market(slips)
    scatter = _profile_scatter(slips)
    odds = _odds_distribution(slips)

    print(
        f"[Analytics] pnl_by_market: {len(pnl)} markets, profile_scatter: {len(scatter)} profiles, odds_distribution: {len(odds)} buckets"
    )

    # Get only profiles that have slips in the database (including 'manual')
    profiles_with_slips = sorted({slip.profile for slip in all_slips})

    return {
        "history": history,
        "market_accuracy": logic.market_accuracy(prof, df_, dt_),
        "pnl_by_market": pnl,
        "odds_distribution": odds,
        "correlation": logic.correlation_data(prof, df_, dt_),
        "profile_scatter": scatter,
        "stats": logic.stats(prof, df_, dt_),
        "profiles": profiles_with_slips,
    }
