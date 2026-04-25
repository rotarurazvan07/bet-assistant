from __future__ import annotations

from fastapi import APIRouter, Request
from utils.profile_utils import get_profile_params

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _get(request: Request):
    return request.app.state.app_logic


def _get_status_value(status) -> str:
    if hasattr(status, "value"):
        return status.value
    return str(status)


# ── Odds distribution ──────────────────────────────────────────────────────────

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
        n = len(batch)
        avg_odds = sum(s.total_odds for s in batch) / n
        win_rate = round((wins / n) * 100, 1)
        implied_win_rate = round(sum(1.0 / s.total_odds for s in batch) / n * 100, 1)
        result.append({
            "range": label,
            "count": n,
            "wins": wins,
            "losses": n - wins,
            "win_rate": win_rate,
            "implied_win_rate": implied_win_rate,
            "avg_odds": round(avg_odds, 2),
            "edge": round(win_rate - implied_win_rate, 1),
        })
    return result


# ── Rolling edge ───────────────────────────────────────────────────────────────

def _rolling_edge(slips, window_days: int = 14) -> list[dict]:
    import pandas as pd

    settled = [
        {
            "date": s.date_generated[:10],
            "won": _get_status_value(s.slip_status) == "Won",
            "implied": 1.0 / s.total_odds if s.total_odds > 0 else 0.0,
        }
        for s in slips
        if _get_status_value(s.slip_status) in ("Won", "Lost")
    ]
    if len(settled) < 3:
        return []

    dates = sorted(set(r["date"] for r in settled))
    result = []
    for date_str in dates:
        end_dt = pd.Timestamp(date_str)
        start_dt = end_dt - pd.Timedelta(days=window_days - 1)
        window = [r for r in settled if start_dt <= pd.Timestamp(r["date"]) <= end_dt]
        if len(window) < 3:
            continue
        wins = sum(1 for r in window if r["won"])
        n = len(window)
        rolling_wr = wins / n * 100
        rolling_implied = sum(r["implied"] for r in window) / n * 100
        result.append({
            "date": date_str,
            "rolling_edge": round(rolling_wr - rolling_implied, 2),
            "rolling_win_rate": round(rolling_wr, 1),
            "rolling_implied": round(rolling_implied, 1),
            "sample_size": n,
        })
    return result


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
        result.append({
            "date": day["date"],
            "drawdown": round(cum - peak, 2),
            "peak": round(peak, 2),
            "cumulative_profit": cum,
        })
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
                data[m] = {"market": m, "legs": 0, "won": 0, "lost": 0,
                            "sum_odds": 0.0, "sum_implied": 0.0, "net_profit": 0.0}
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
        result.append({
            "market": m,
            "legs": total,
            "won": d["won"],
            "lost": d["lost"],
            "win_rate": win_rate,
            "implied_win_rate": implied,
            "edge": round(win_rate - implied, 1),
            "avg_odds": round(d["sum_odds"] / total, 2) if total else 0.0,
            "net_profit": round(d["net_profit"], 2),
        })
    return sorted(result, key=lambda x: x["edge"], reverse=True)


# ── Return distribution histogram ─────────────────────────────────────────────

def _return_distribution(slips) -> dict:
    settled = [s for s in slips if _get_status_value(s.slip_status) in ("Won", "Lost")]
    if not settled:
        return {"bins": [], "mean": 0.0, "median": 0.0}

    pnls = [
        round((s.total_odds - 1) * s.units, 2)
        if _get_status_value(s.slip_status) == "Won"
        else round(-s.units, 2)
        for s in settled
    ]
    n = len(pnls)
    mean_val = round(sum(pnls) / n, 2)
    sorted_p = sorted(pnls)
    median_val = round(
        sorted_p[n // 2] if n % 2 else (sorted_p[n // 2 - 1] + sorted_p[n // 2]) / 2, 2
    )

    min_p, max_p = min(pnls), max(pnls)
    if min_p == max_p:
        return {"bins": [{"range": f"{min_p:.1f}", "count": n, "is_positive": min_p >= 0}],
                "mean": mean_val, "median": median_val}

    n_bins = min(12, max(5, n // 3))
    step = (max_p - min_p) / n_bins
    bin_counts: dict[int, int] = {}
    for p in pnls:
        idx = min(int((p - min_p) / step), n_bins - 1)
        bin_counts[idx] = bin_counts.get(idx, 0) + 1

    bins = []
    for i in range(n_bins):
        lo = round(min_p + i * step, 1)
        hi = round(lo + step, 1)
        cnt = bin_counts.get(i, 0)
        if cnt > 0:
            bins.append({"range": f"{lo:.1f}", "range_end": f"{hi:.1f}",
                         "count": cnt, "is_positive": lo >= 0})

    return {"bins": bins, "mean": mean_val, "median": median_val}


# ── Time patterns (day-of-week + hour) ────────────────────────────────────────

def _time_patterns(slips) -> dict:
    from datetime import datetime as dt_cls

    DOW_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow_data: dict[str, dict] = {}
    hour_data: dict[str, dict] = {}

    for slip in slips:
        if _get_status_value(slip.slip_status) not in ("Won", "Lost"):
            continue
        for leg in slip.legs:
            if _get_status_value(leg.status) not in ("Won", "Lost"):
                continue
            if not leg.datetime:
                continue
            try:
                if hasattr(leg.datetime, "weekday"):
                    dt = leg.datetime
                else:
                    raw = str(leg.datetime)
                    try:
                        dt = dt_cls.fromisoformat(raw)
                    except Exception:
                        dt = dt_cls.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")

                dow = dt.strftime("%a")
                hour_bucket = f"{(dt.hour // 2) * 2:02d}:00"
                is_won = _get_status_value(leg.status) == "Won"

                for container, key in [(dow_data, dow), (hour_data, hour_bucket)]:
                    if key not in container:
                        container[key] = {"key": key, "total": 0, "won": 0}
                    container[key]["total"] += 1
                    if is_won:
                        container[key]["won"] += 1
            except Exception:
                continue

    def finalize(d: dict) -> list[dict]:
        result = []
        for v in d.values():
            v["win_rate"] = round(v["won"] / v["total"] * 100, 1) if v["total"] else 0.0
            result.append(v)
        return result

    dow_list = sorted(
        finalize(dow_data),
        key=lambda x: DOW_ORDER.index(x["key"]) if x["key"] in DOW_ORDER else 7,
    )
    hour_list = sorted(finalize(hour_data), key=lambda x: x["key"])
    return {"day_of_week": dow_list, "hour": hour_list}


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

    history = logic.daily_summary(prof, df_, dt_)
    slips = logic.get_slips(prof, df_, dt_)
    all_slips = logic.get_slips(None, df_, dt_)

    return {
        "history": history,
        "market_accuracy": logic.market_accuracy(prof, df_, dt_),
        "pnl_by_market": _pnl_by_market(slips),
        "odds_distribution": _odds_distribution(slips),
        "correlation": logic.correlation_data(prof, df_, dt_),
        "profile_scatter": _profile_scatter(slips),
        "stats": logic.stats(prof, df_, dt_),
        "profiles": sorted({slip.profile for slip in all_slips}),
        # ── Phase 1 additions ──────────────────────────────────────────
        "rolling_edge": _rolling_edge(slips),
        "drawdown": _drawdown_data(history),
        "odds_distribution": _odds_distribution(slips),  # now includes implied_win_rate
        # ── Phase 2 additions ──────────────────────────────────────────
        "market_breakdown": _market_breakdown(slips),
        # ── Phase 3 additions ──────────────────────────────────────────
        "return_distribution": _return_distribution(slips),
        "time_patterns": _time_patterns(slips),
    }