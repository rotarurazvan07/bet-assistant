"""
Analytics utilities for calculating betting statistics and metrics.
This module contains pure functions for analytics calculations.
"""

from datetime import datetime, timedelta
from typing import Any, List, Dict, Union
import pandas as pd


def calculate_overall_edge(slips) -> float:
    """
    Calculate overall edge for slips.

    Parameters:
    slips: List of settled slips

    Returns:
    float: Overall edge value
    """
    if not slips:
        return 0.0

    # Filter for settled slips (Won or Lost)
    settled = [s for s in slips if hasattr(s, 'slip_status') and _get_status_value(s.slip_status) in ("Won", "Lost")]

    if not settled:
        return 0.0

    n_won = len([s for s in settled if _get_status_value(s.slip_status) == "Won"])
    n_settled = len(settled)
    actual_win_rate = round((n_won / n_settled * 100) if n_settled else 0.0, 2)
    implied_win_rate = round(
        (sum(1.0 / s.total_odds for s in settled if s.total_odds > 0) / n_settled * 100)
        if n_settled else 0.0, 2
    )

    return round(actual_win_rate - implied_win_rate, 2)


def calculate_rolling_edge(slips, window_days: int) -> List[Dict[str, Any]]:
    """
    Calculate rolling edge for slips over a specified window.

    Parameters:
    slips: List of settled slips
    window_days: Number of days for the rolling window

    Returns:
    list of dicts with rolling edge data points
    """
    import pandas as pd

    # Filter for settled slips (Won or Lost)
    settled = [s for s in slips if hasattr(s, 'slip_status') and _get_status_value(s.slip_status) in ("Won", "Lost")]

    if not settled:
        return []

    # Prepare data for rolling calculation
    settled_data = [
        {
            "date": s.date_generated[:10],
            "won": _get_status_value(s.slip_status) == "Won",
            "implied": 1.0 / s.total_odds if s.total_odds > 0 else 0.0,
        }
        for s in settled
    ]

    dates = sorted(set(r["date"] for r in settled_data))
    result = []

    for date_str in dates:
        end_dt = pd.Timestamp(date_str)
        start_dt = end_dt - pd.Timedelta(days=window_days - 1)
        window = [r for r in settled_data if start_dt <= pd.Timestamp(r["date"]) <= end_dt]

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


def calculate_kelly_recommendation(n_won, n_settled, avg_odds, current_bankroll) -> float:
    """Calculates suggested units based on historical performance and current liquid funds."""
    if n_settled == 0 or avg_odds <= 1:
        return 0.0

    win_rate = n_won / n_settled
    b = avg_odds - 1  # Net odds
    p = win_rate
    q = 1 - p

    # Kelly % = (bp - q) / b
    kelly_fraction = (b * p - q) / b

    # Apply the fraction to the current gross_return (treated as bankroll)
    # Using 100 as a floor to prevent 0 units if gross_return is small/zero
    # effective_bankroll = max(current_bankroll, 100.0)
    suggested_units = kelly_fraction * current_bankroll if kelly_fraction > 0 else 0.0

    return round(suggested_units, 2)


def get_rolling_edge_trend(settled_slips) -> dict:
    """Analyzes the edge trend over the last 14 days."""
    today = datetime.now()
    fourteen_days_ago = today - timedelta(days=14)

    # Filter slips from the last 14 days
    recent_slips = [
        s for s in settled_slips
        if datetime.strptime(s.date_generated[:10], "%Y-%m-%d") >= fourteen_days_ago
    ]

    if not recent_slips:
        return {"trend": "neutral", "value": 0.0}

    # Split into two 7-day buckets to find the trend
    seven_days_ago = today - timedelta(days=7)
    week_1 = [s for s in recent_slips if datetime.strptime(s.date_generated[:10], "%Y-%m-%d") < seven_days_ago]
    week_2 = [s for s in recent_slips if datetime.strptime(s.date_generated[:10], "%Y-%m-%d") >= seven_days_ago]

    edge_1 = calculate_overall_edge(week_1)
    edge_2 = calculate_overall_edge(week_2)

    diff = edge_2 - edge_1
    if diff > 0.02:
        trend = "growing"
    elif diff < -0.02:
        trend = "declining"
    else:
        trend = "stable"

    return {"trend": trend, "value": round(edge_2, 2)}


def _get_status_value(status) -> str:
    """Extract value from enum or return string representation."""
    if hasattr(status, "value"):
        return status.value
    return str(status)


def calculate_daily_summary(
    slips,
    profile: str | list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None
) -> list[dict[str, Any]]:
    from bet_framework.core.types import Outcome

    settled_slips = [s for s in slips if _get_status_value(s.slip_status) in ("Won", "Lost")]
    settled_slips.sort(key=lambda x: x.date_generated)

    daily_stats = {}
    for s in settled_slips:
        day = s.date_generated
        if day not in daily_stats:
            daily_stats[day] = {
                "date": day,
                "slips_count": 0,
                "units_bet": 0.0,
                "units_won": 0.0,
                "won_count": 0,
            }

        stats = daily_stats[day]
        stats["slips_count"] += 1
        stats["units_bet"] += s.units
        if s.slip_status == Outcome.WON:
            stats["units_won"] += s.total_odds * s.units
            stats["won_count"] += 1

    summary = []
    cum_bet = 0.0
    cum_profit = 0.0
    cum_won_count = 0
    cum_settled_count = 0

    sorted_days = sorted(daily_stats.keys())
    for day in sorted_days:
        stats = daily_stats[day]
        profit = stats["units_won"] - stats["units_bet"]

        cum_bet += stats["units_bet"]
        cum_profit += profit
        cum_won_count += stats["won_count"]
        cum_settled_count += stats["slips_count"]

        summary.append(
            {
                "date": day,
                "slips_count": stats["slips_count"],
                "units_bet": round(stats["units_bet"], 2),
                "units_won": round(stats["units_won"], 2),
                "net_profit": round(profit, 2),
                "cumulative_profit": round(cum_profit, 2),
                "cumulative_bet": round(cum_bet, 2),
                "roi_percentage": round((cum_profit / cum_bet * 100) if cum_bet else 0, 2),
                "win_rate": round(
                    (cum_won_count / cum_settled_count * 100) if cum_settled_count else 0,
                    2,
                ),
            }
        )

    return summary


def calculate_market_accuracy(slips) -> list[dict[str, Any]]:
    market_stats = {}
    for slip in slips:
        for leg in slip.legs:
            leg_status = _get_status_value(leg.status)
            if leg_status not in ("Won", "Lost"):
                continue

            mtype = leg.market or "Unknown"
            if mtype not in market_stats:
                market_stats[mtype] = {
                    "market": mtype,
                    "won": 0,
                    "lost": 0,
                    "total": 0,
                }

            market_stats[mtype]["total"] += 1
            if leg_status == "Won":
                market_stats[mtype]["won"] += 1
            else:
                market_stats[mtype]["lost"] += 1

    results = []
    for m in market_stats.values():
        m["accuracy"] = round((m["won"] / m["total"] * 100) if m["total"] else 0, 2)
        results.append(m)

    return sorted(results, key=lambda x: x["total"], reverse=True)


def calculate_correlation_data(slips) -> list[dict[str, Any]]:
    data = []
    for s in slips:
        slip_status = _get_status_value(s.slip_status)
        if slip_status in ("Won", "Lost"):
            data.append(
                {
                    "legs_count": len(s.legs),
                    "total_odds": round(s.total_odds, 2),
                    "units": s.units,
                    "status": slip_status,
                    "profit": round(
                        (s.total_odds * s.units - s.units) if slip_status == "Won" else -s.units,
                        2,
                    ),
                }
            )
    return data


def calculate_streak_metrics(slips) -> dict:
    """
    Calculate streak-related metrics from slips based on daily P&L.
    
    A "winning day" has positive net profit, a "losing day" has negative net profit.
    Break-even days (zero P&L) are ignored and don't break streaks.
    Pending and Live slips are excluded from daily P&L calculations.
    
    Parameters:
    slips: List of slips (all statuses)
    
    Returns:
    dict with current_streak (days), longest_win_streak (days), longest_loss_streak (days)
    """
    if not slips:
        return {
            "current_streak": 0,
            "longest_win_streak": 0,
            "longest_loss_streak": 0
        }
    
    # Filter for settled slips only (Won or Lost) - Pending/Live excluded from P&L
    settled_slips = [s for s in slips if _get_status_value(s.slip_status) in ("Won", "Lost")]
    
    if not settled_slips:
        return {
            "current_streak": 0,
            "longest_win_streak": 0,
            "longest_loss_streak": 0
        }
    
    # Group slips by date and calculate daily P&L
    daily_pnl = {}
    for slip in settled_slips:
        # Extract date part from date_generated (ISO string)
        date_str = slip.date_generated.split('T')[0] if 'T' in slip.date_generated else slip.date_generated
        date = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Calculate slip profit/loss
        if _get_status_value(slip.slip_status) == "Won":
            profit = (slip.total_odds - 1) * slip.units
        else:  # Lost
            profit = -slip.units
        
        daily_pnl[date] = daily_pnl.get(date, 0) + profit
    
    # Sort dates in descending order (newest first) for current streak
    sorted_dates = sorted(daily_pnl.keys(), reverse=True)
    
    # Calculate current streak: consecutive days from newest with same sign
    current_streak = 0
    current_streak_type = None  # 'win' or 'loss'
    
    for date in sorted_dates:
        pnl = daily_pnl[date]
        if pnl == 0:
            continue  # Break-even days don't count and don't break streak
        
        day_type = 'win' if pnl > 0 else 'loss'
        
        if current_streak_type is None:
            current_streak_type = day_type
            current_streak = 1
        elif day_type == current_streak_type:
            current_streak += 1
        else:
            break  # Streak broken
    
    # For longest streaks, we need to consider all days in chronological order
    chronological_dates = sorted(daily_pnl.keys())
    
    longest_win_streak = 0
    longest_loss_streak = 0
    win_streak = 0
    loss_streak = 0
    
    for date in chronological_dates:
        pnl = daily_pnl[date]
        if pnl == 0:
            continue  # Skip break-even days
        
        if pnl > 0:
            win_streak += 1
            loss_streak = 0
            longest_win_streak = max(longest_win_streak, win_streak)
        else:  # pnl < 0
            loss_streak += 1
            win_streak = 0
            longest_loss_streak = max(longest_loss_streak, loss_streak)
    
    # Apply sign to current_streak: positive for win streak, negative for loss streak
    if current_streak_type == 'win':
        current_streak = current_streak  # positive
    elif current_streak_type == 'loss':
        current_streak = -current_streak  # negative
    else:
        current_streak = 0
    
    return {
        "current_streak": current_streak,
        "longest_win_streak": longest_win_streak,
        "longest_loss_streak": longest_loss_streak
    }


def calculate_profit_factor(settled_slips) -> float:
    """
    Calculate profit factor = sum(wins) / abs(sum(losses))
    
    Parameters:
    settled_slips: List of settled slips (Won or Lost)
    
    Returns:
    float: profit factor, 0.0 if no losses
    """
    if not settled_slips:
        return 0.0
    
    total_wins = 0.0
    total_losses = 0.0
    
    for slip in settled_slips:
        status = _get_status_value(slip.slip_status)
        if status not in ("Won", "Lost"):
            continue
        
        # Calculate slip profit
        if status == "Won":
            profit = (slip.total_odds * slip.units) - slip.units
            total_wins += profit
        else:  # Lost
            loss = slip.units
            total_losses += loss
    
    if total_losses == 0:
        return 0.0
    
    profit_factor = total_wins / total_losses
    return round(profit_factor, 2)


def calculate_biggest_win_loss(settled_slips) -> dict:
    """
    Calculate biggest win and biggest loss from settled slips.
    
    Parameters:
    settled_slips: List of settled slips (Won or Lost)
    
    Returns:
    dict with biggest_win_units and biggest_loss_units
    """
    if not settled_slips:
        return {
            "biggest_win_units": None,
            "biggest_loss_units": None
        }
    
    biggest_win = None
    biggest_loss = None
    
    for slip in settled_slips:
        status = _get_status_value(slip.slip_status)
        if status not in ("Won", "Lost"):
            continue
        
        # Calculate slip net profit
        if status == "Won":
            profit = (slip.total_odds * slip.units) - slip.units
            if biggest_win is None or profit > biggest_win:
                biggest_win = profit
        else:  # Lost
            loss = -slip.units  # Negative value
            if biggest_loss is None or loss < biggest_loss:
                biggest_loss = loss
    
    return {
        "biggest_win_units": round(biggest_win, 2) if biggest_win is not None else None,
        "biggest_loss_units": round(biggest_loss, 2) if biggest_loss is not None else None
    }